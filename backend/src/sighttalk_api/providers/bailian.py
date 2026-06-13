"""Alibaba Cloud Model Studio Bailian realtime provider adapter."""

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

DEFAULT_REALTIME_MODEL = "qwen3-omni-flash-realtime"
DEFAULT_REALTIME_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
LEGACY_REALTIME_MODEL = "multimodal-dialog"
CONNECT_ATTEMPTS = 3
CONNECT_RETRY_DELAY_SECONDS = 0.5
IMAGE_INPUT_GATE_CLOSE_EVENTS = {
    "input_audio_buffer.speech_stopped",
    "input_audio_buffer.committed",
    "input_audio_buffer.cleared",
    "response.created",
    "response.done",
    "response.completed",
    "response.cancelled",
    "response.failed",
}


class BailianRealtimeProvider(AIProvider):
    """Bailian realtime WebSocket adapter.

    The adapter keeps the vendor wire format isolated. The outgoing messages use a
    conservative JSON shape and can be adjusted as Bailian account/model details are
    finalized without changing the application-level contracts.
    """

    def __init__(
        self,
        *,
        api_key: str,
        realtime_url: str,
        region: str,
        workspace_id: str,
        model: str,
        turn_silence_duration_ms: int = 800,
        manual_response_enabled: bool = False,
    ) -> None:
        self._api_key = api_key
        self._realtime_url = normalize_realtime_url(realtime_url)
        self._region = region
        self._workspace_id = workspace_id
        self._model = normalize_realtime_model(model)
        self._turn_silence_duration_ms = turn_silence_duration_ms
        self._manual_response_enabled = manual_response_enabled
        self._connection: ClientConnection | None = None
        self._audio_buffer_accepts_images = False
        self._send_lock = asyncio.Lock()
        self._closed = False

    def capabilities(self) -> ProviderCapabilities:
        """Return capabilities supported by the Bailian realtime VAD flow."""
        return ProviderCapabilities()

    async def connect(self, session: ProviderSessionConfig) -> None:
        """Open the realtime WebSocket and configure model session behavior."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }
        if self._workspace_id:
            headers["X-DashScope-WorkSpace"] = self._workspace_id
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
                            "voice": "Cherry",
                            "input_audio_format": "pcm",
                            "output_audio_format": "pcm",
                            "instructions": session.system_prompt,
                            "turn_detection": {
                                "type": "server_vad",
                                "threshold": 0.5,
                                "silence_duration_ms": self._turn_silence_duration_ms,
                                "create_response": True,
                                "interrupt_response": True,
                            },
                        },
                    },
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
        """Update provider instructions before explicit response creation."""
        await self._send_json(
            {
                "event_id": new_event_id(),
                "type": "session.update",
                "session": {
                    "instructions": context.system_prompt,
                },
            }
        )

    async def create_response(self) -> None:
        """Explicitly ask the provider to create an assistant response."""
        return

    async def send_audio(self, chunk: AudioChunk) -> None:
        """Append base64-encoded PCM audio to the provider input buffer."""
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
        """Append a JPEG while the current audio buffer is still open."""
        async with self._send_lock:
            if not self._audio_buffer_accepts_images:
                return False
            await self._send_json_unlocked(
                {
                    "event_id": new_event_id(),
                    "type": "input_image_buffer.append",
                    "image": base64.b64encode(frame.data).decode("ascii"),
                }
            )
            return True

    async def send_control(self, event: ControlEvent) -> None:
        """Translate provider-neutral control events to Bailian realtime commands."""
        if event.type == "interrupt":
            self._audio_buffer_accepts_images = False
            await self._send_json({"event_id": new_event_id(), "type": "response.cancel"})

    async def events(self) -> AsyncIterator[ProviderEvent]:
        """Yield normalized provider events until the connection is closed."""
        if self._connection is None:
            yield ProviderEvent(
                type="error",
                code="PROVIDER_CONFIGURATION_ERROR",
                message="Bailian provider is not connected",
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
        """Best-effort close used by retries and normal shutdown."""
        self._audio_buffer_accepts_images = False
        if self._connection is not None:
            with suppress(Exception):
                await self._connection.close()
            self._connection = None

    async def _send_json(self, payload: dict[str, Any]) -> None:
        """Send one vendor payload, converting connection loss into RuntimeError."""
        async with self._send_lock:
            await self._send_json_unlocked(payload)

    async def _send_json_unlocked(self, payload: dict[str, Any]) -> None:
        """Send one vendor payload while the caller holds any required ordering lock."""
        if self._connection is None:
            raise RuntimeError("Bailian realtime provider is not connected")
        try:
            await self._connection.send(json.dumps(payload))
        except ConnectionClosed as exc:
            self._connection = None
            raise RuntimeError(provider_unavailable_message(exc)) from exc

    def _map_event(self, payload: dict[str, Any]) -> ProviderEvent | None:
        """Map Bailian realtime wire events to provider-neutral events."""
        event_type = str(payload.get("type", ""))
        if should_close_image_input_gate(event_type):
            self._audio_buffer_accepts_images = False
        text = str(payload.get("text", ""))
        stash = str(payload.get("stash", ""))
        message_id = str(
            payload.get("message_id") or payload.get("item_id") or payload.get("response_id") or ""
        )

        if event_type in {"transcript.delta", "conversation.item.input_audio_transcription.delta"}:
            return ProviderEvent(
                type="transcript_delta",
                speaker="user",
                text=text + stash or str(payload.get("delta", "")),
                message_id=message_id,
            )
        if event_type in {
            "transcript.done",
            "conversation.item.input_audio_transcription.completed",
        }:
            return ProviderEvent(
                type="transcript_done",
                speaker="user",
                text=text or str(payload.get("transcript", "")),
                message_id=message_id,
            )
        if event_type in {
            "response.text.delta",
            "response.audio_transcript.delta",
        }:
            return ProviderEvent(
                type="transcript_delta",
                speaker="assistant",
                text=text or str(payload.get("delta", "")) or str(payload.get("transcript", "")),
                message_id=message_id,
            )
        if event_type in {"response.audio_transcript.done", "response.text.done"}:
            return ProviderEvent(
                type="transcript_done",
                speaker="assistant",
                text=text or str(payload.get("transcript", "")) or str(payload.get("delta", "")),
                message_id=message_id,
            )
        if event_type in {"response.audio.delta", "response.output_audio.delta"}:
            encoded = str(payload.get("delta", payload.get("audio", "")))
            audio = base64.b64decode(encoded) if encoded else b""
            return ProviderEvent(
                type="audio_delta",
                audio=audio,
                mime_type=str(payload.get("mime_type", "audio/pcm;rate=24000")),
                message_id=message_id,
            )
        if event_type in {"response.done", "response.completed"}:
            return ProviderEvent(type="response_done", message_id=message_id)
        if event_type in {"error", "session.error"}:
            error = payload.get("error")
            error_payload = error if isinstance(error, dict) else payload
            if is_stale_image_protocol_error(error_payload):
                self._audio_buffer_accepts_images = False
                return None
            return ProviderEvent(
                type="error",
                code=str(error_payload.get("code", "PROVIDER_PROTOCOL_ERROR")),
                message=str(error_payload.get("message", "Provider error")),
            )
        return None


def realtime_url_with_model(base_url: str, model: str) -> str:
    """Return a realtime URL with the requested normalized model query parameter."""
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["model"] = normalize_realtime_model(model)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def new_event_id() -> str:
    """Create an opaque provider event id for outbound realtime messages."""
    return f"event_{uuid.uuid4().hex}"


def normalize_realtime_url(url: str) -> str:
    """Normalize legacy Bailian inference URLs to the realtime endpoint."""
    if not url:
        return DEFAULT_REALTIME_URL
    if url.endswith("/inference"):
        return f"{url.removesuffix('/inference')}/realtime"
    return url


def normalize_realtime_model(model: str) -> str:
    """Normalize empty or legacy realtime model names to the supported default."""
    if not model or model == LEGACY_REALTIME_MODEL:
        return DEFAULT_REALTIME_MODEL
    return model


def should_close_image_input_gate(event_type: str) -> bool:
    """Return whether a server event closes the current image append window."""
    return event_type in IMAGE_INPUT_GATE_CLOSE_EVENTS


def is_stale_image_protocol_error(error_payload: dict[Any, Any]) -> bool:
    """Return whether an error is a recoverable stale optional image frame."""
    code = str(error_payload.get("code", "")).lower()
    message = str(error_payload.get("message", "")).lower()
    return (
        "protocol" in code
        and "append image before append audio" in message
    )


def provider_unavailable_message(exc: Exception) -> str:
    """Build a stable error message for provider connection failures."""
    detail = str(exc).strip() or exc.__class__.__name__
    return f"Bailian realtime provider unavailable: {detail}"
