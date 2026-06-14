"""OpenAI Realtime provider adapter."""

from __future__ import annotations

import asyncio
import base64
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed

from sighttalk_api.providers.base import (
    AIProvider,
    AudioChunk,
    ControlEvent,
    ImageFrame,
    ProviderCapabilities,
    ProviderContext,
    ProviderEvent,
    ProviderSessionConfig,
)

DEFAULT_REALTIME_MODEL = "gpt-realtime"
DEFAULT_REALTIME_URL = "wss://api.openai.com/v1/realtime"
CONNECT_ATTEMPTS = 3
CONNECT_RETRY_DELAY_SECONDS = 0.5


class OpenAIRealtimeProvider(AIProvider):
    """OpenAI Realtime WebSocket adapter."""

    def __init__(
        self,
        *,
        api_key: str,
        realtime_url: str,
        model: str,
        voice: str = "alloy",
    ) -> None:
        self._api_key = api_key
        self._realtime_url = normalize_realtime_url(realtime_url)
        self._model = model or DEFAULT_REALTIME_MODEL
        self._voice = voice
        self._connection: ClientConnection | None = None
        self._send_lock = asyncio.Lock()
        self._closed = False
        self._audio_buffer_accepts_images = False

    def capabilities(self) -> ProviderCapabilities:
        """OpenAI Realtime uses server VAD for automatic response creation."""
        return ProviderCapabilities()

    async def connect(self, session: ProviderSessionConfig) -> None:
        """Open the realtime WebSocket and configure the session."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "OpenAI-Beta": "realtime=v1",
        }
        url = realtime_url_with_model(self._realtime_url, session.model or self._model)
        last_error: Exception | None = None
        for attempt in range(1, CONNECT_ATTEMPTS + 1):
            try:
                self._connection = await websockets.connect(
                    url,
                    additional_headers=headers,
                    ping_interval=20,
                    ping_timeout=20,
                )
                self._audio_buffer_accepts_images = False
                await self._send_json(
                    {
                        "event_id": new_event_id(),
                        "type": "session.update",
                        "session": {
                            "modalities": ["text", "audio"],
                            "instructions": session.system_prompt,
                            "voice": self._voice,
                            "input_audio_format": "pcm16",
                            "output_audio_format": "pcm16",
                            "turn_detection": {
                                "type": "server_vad",
                                "create_response": True,
                                "interrupt_response": True,
                            },
                        },
                    }
                )
                return
            except Exception as exc:
                last_error = exc
                await self._close_connection()
                if attempt < CONNECT_ATTEMPTS:
                    await asyncio.sleep(CONNECT_RETRY_DELAY_SECONDS * attempt)
        if last_error is not None:
            raise RuntimeError(provider_unavailable_message(last_error)) from last_error

    async def update_context(self, context: ProviderContext) -> None:
        """Update provider instructions for future responses."""
        await self._send_json(
            {
                "event_id": new_event_id(),
                "type": "session.update",
                "session": {"instructions": context.system_prompt},
            }
        )

    async def create_response(self) -> None:
        """Explicit response creation is not used in the automatic VAD flow."""
        return

    async def send_audio(self, chunk: AudioChunk) -> None:
        """Append base64-encoded PCM16 audio to the input audio buffer."""
        async with self._send_lock:
            await self._send_json_unlocked(
                {
                    "event_id": new_event_id(),
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(chunk.data).decode("ascii"),
                }
            )
            self._audio_buffer_accepts_images = True

    async def send_image(self, frame: ImageFrame) -> bool:
        """Send one camera frame as a user conversation item when audio is active."""
        async with self._send_lock:
            if not self._audio_buffer_accepts_images:
                return False
            image_url = (
                f"data:{frame.mime_type};base64,"
                f"{base64.b64encode(frame.data).decode('ascii')}"
            )
            await self._send_json_unlocked(
                {
                    "event_id": new_event_id(),
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_image", "image_url": image_url}],
                    },
                }
            )
            return True

    async def send_control(self, event: ControlEvent) -> None:
        """Translate provider-neutral control events to OpenAI realtime commands."""
        if event.type == "interrupt":
            self._audio_buffer_accepts_images = False
            await self._send_json({"event_id": new_event_id(), "type": "response.cancel"})

    async def events(self) -> AsyncIterator[ProviderEvent]:
        """Yield normalized provider events until the connection closes."""
        if self._connection is None:
            yield ProviderEvent(
                type="error",
                code="PROVIDER_CONFIGURATION_ERROR",
                message="OpenAI realtime provider is not connected",
            )
            return

        while not self._closed:
            try:
                raw = await self._connection.recv()
                event = self._map_event(json.loads(str(raw)))
                if event is not None:
                    yield event
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                yield ProviderEvent(
                    type="error",
                    code="PROVIDER_PROTOCOL_ERROR",
                    message=str(exc),
                )
                return

    async def close(self) -> None:
        """Close the provider connection and stop the event stream."""
        self._closed = True
        await self._close_connection()

    async def _close_connection(self) -> None:
        self._audio_buffer_accepts_images = False
        if self._connection is not None:
            with suppress(Exception):
                await self._connection.close()
            self._connection = None

    async def _send_json(self, payload: dict[str, Any]) -> None:
        async with self._send_lock:
            await self._send_json_unlocked(payload)

    async def _send_json_unlocked(self, payload: dict[str, Any]) -> None:
        if self._connection is None:
            raise RuntimeError("OpenAI realtime provider is not connected")
        try:
            await self._connection.send(json.dumps(payload))
        except ConnectionClosed as exc:
            self._connection = None
            raise RuntimeError(provider_unavailable_message(exc)) from exc

    def _map_event(self, payload: dict[str, Any]) -> ProviderEvent | None:
        event_type = str(payload.get("type", ""))
        message_id = str(
            payload.get("item_id") or payload.get("message_id") or payload.get("response_id") or ""
        )
        if event_type in {
            "input_audio_buffer.committed",
            "input_audio_buffer.cleared",
            "response.created",
            "response.done",
            "response.cancelled",
            "response.failed",
        }:
            self._audio_buffer_accepts_images = False

        if event_type == "session.created" or event_type == "session.updated":
            return ProviderEvent(type="status", status="listening")
        if event_type == "response.created":
            return ProviderEvent(type="status", status="thinking")
        if event_type in {
            "conversation.item.input_audio_transcription.delta",
            "input_audio_transcription.delta",
        }:
            return ProviderEvent(
                type="transcript_delta",
                speaker="user",
                text=str(payload.get("delta", "")),
                message_id=message_id,
            )
        if event_type in {
            "conversation.item.input_audio_transcription.completed",
            "input_audio_transcription.completed",
        }:
            return ProviderEvent(
                type="transcript_done",
                speaker="user",
                text=str(payload.get("transcript", "")),
                message_id=message_id,
            )
        if event_type in {"response.audio_transcript.delta", "response.output_text.delta"}:
            return ProviderEvent(
                type="transcript_delta",
                speaker="assistant",
                text=str(payload.get("delta", "")),
                message_id=message_id,
            )
        if event_type in {"response.audio_transcript.done", "response.output_text.done"}:
            return ProviderEvent(
                type="transcript_done",
                speaker="assistant",
                text=str(payload.get("transcript") or payload.get("text") or ""),
                message_id=message_id,
            )
        if event_type in {"response.audio.delta", "response.output_audio.delta"}:
            encoded = str(payload.get("delta", ""))
            return ProviderEvent(
                type="audio_delta",
                audio=base64.b64decode(encoded) if encoded else b"",
                mime_type="audio/pcm;rate=24000",
                message_id=message_id,
            )
        if event_type == "response.done":
            return ProviderEvent(type="response_done", message_id=message_id)
        if event_type == "error":
            error = payload.get("error")
            error_payload = error if isinstance(error, dict) else payload
            return ProviderEvent(
                type="error",
                code=str(error_payload.get("code", "PROVIDER_PROTOCOL_ERROR")),
                message=str(error_payload.get("message", "Provider error")),
            )
        return None


def realtime_url_with_model(base_url: str, model: str) -> str:
    """Return a realtime URL with the requested model query parameter."""
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["model"] = model or DEFAULT_REALTIME_MODEL
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def normalize_realtime_url(url: str) -> str:
    """Return the configured URL or the OpenAI realtime endpoint."""
    return url or DEFAULT_REALTIME_URL


def new_event_id() -> str:
    """Create an opaque provider event id."""
    return f"event_{uuid.uuid4().hex}"


def provider_unavailable_message(exc: Exception) -> str:
    """Build a stable error message for provider connection failures."""
    detail = str(exc).strip() or exc.__class__.__name__
    return f"OpenAI realtime provider unavailable: {detail}"
