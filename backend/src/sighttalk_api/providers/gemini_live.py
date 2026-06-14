"""Google Gemini Live provider adapter."""

from __future__ import annotations

import asyncio
import base64
import json
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

DEFAULT_LIVE_MODEL = "gemini-2.0-flash-live-001"
DEFAULT_LIVE_URL = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
)
CONNECT_ATTEMPTS = 3
CONNECT_RETRY_DELAY_SECONDS = 0.5


class GeminiLiveProvider(AIProvider):
    """Gemini Live WebSocket adapter."""

    def __init__(
        self,
        *,
        api_key: str,
        live_url: str,
        model: str,
        voice: str = "Zephyr",
    ) -> None:
        self._api_key = api_key
        self._live_url = live_url or DEFAULT_LIVE_URL
        self._model = model or DEFAULT_LIVE_MODEL
        self._voice = voice
        self._connection: ClientConnection | None = None
        self._send_lock = asyncio.Lock()
        self._closed = False
        self._audio_started = False
        self._current_response_id = ""

    def capabilities(self) -> ProviderCapabilities:
        """Gemini Live creates responses through the live session turn flow."""
        return ProviderCapabilities()

    async def connect(self, session: ProviderSessionConfig) -> None:
        """Open the Gemini Live WebSocket and send the required setup message."""
        last_error: Exception | None = None
        for attempt in range(1, CONNECT_ATTEMPTS + 1):
            try:
                self._connection = await websockets.connect(
                    live_url_with_key(self._live_url, self._api_key),
                    ping_interval=20,
                    ping_timeout=20,
                )
                await self._send_json(
                    {
                        "setup": {
                            "model": normalize_model_name(session.model or self._model),
                            "system_instruction": {
                                "parts": [{"text": session.system_prompt}],
                            },
                            "generation_config": {
                                "response_modalities": ["AUDIO"],
                                "speech_config": {
                                    "voice_config": {
                                        "prebuilt_voice_config": {
                                            "voice_name": self._voice,
                                        }
                                    }
                                },
                            },
                            "input_audio_transcription": {},
                            "output_audio_transcription": {},
                        }
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
        """Gemini Live does not support mid-session system prompt replacement here."""
        await self._send_json(
            {
                "client_content": {
                    "turns": [
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": (
                                        "Use this updated context as non-user-visible guidance: "
                                        f"{context.system_prompt}"
                                    )
                                }
                            ],
                        }
                    ],
                    "turn_complete": False,
                }
            }
        )

    async def create_response(self) -> None:
        """Explicit response creation is not used in the live realtime flow."""
        return

    async def send_audio(self, chunk: AudioChunk) -> None:
        """Append one PCM audio chunk to the live realtime input stream."""
        async with self._send_lock:
            await self._send_json_unlocked(
                {
                    "realtime_input": {
                        "media_chunks": [
                            {
                                "mime_type": f"audio/pcm;rate={chunk.sample_rate}",
                                "data": base64.b64encode(chunk.data).decode("ascii"),
                            }
                        ]
                    }
                }
            )
            self._audio_started = True

    async def send_image(self, frame: ImageFrame) -> bool:
        """Append one JPEG frame after audio has started."""
        async with self._send_lock:
            if not self._audio_started:
                return False
            await self._send_json_unlocked(
                {
                    "realtime_input": {
                        "media_chunks": [
                            {
                                "mime_type": frame.mime_type,
                                "data": base64.b64encode(frame.data).decode("ascii"),
                            }
                        ]
                    }
                }
            )
            return True

    async def send_control(self, event: ControlEvent) -> None:
        """Translate provider-neutral control events to Gemini Live commands."""
        if event.type == "interrupt":
            self._audio_started = False
            await self._send_json({"realtime_input": {"activity_end": {}}})

    async def events(self) -> AsyncIterator[ProviderEvent]:
        """Yield normalized provider events until the connection closes."""
        if self._connection is None:
            yield ProviderEvent(
                type="error",
                code="PROVIDER_CONFIGURATION_ERROR",
                message="Gemini live provider is not connected",
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
        self._audio_started = False
        if self._connection is not None:
            with suppress(Exception):
                await self._connection.close()
            self._connection = None

    async def _send_json(self, payload: dict[str, Any]) -> None:
        async with self._send_lock:
            await self._send_json_unlocked(payload)

    async def _send_json_unlocked(self, payload: dict[str, Any]) -> None:
        if self._connection is None:
            raise RuntimeError("Gemini live provider is not connected")
        try:
            await self._connection.send(json.dumps(payload))
        except ConnectionClosed as exc:
            self._connection = None
            raise RuntimeError(provider_unavailable_message(exc)) from exc

    def _map_event(self, payload: dict[str, Any]) -> ProviderEvent | None:
        if "setupComplete" in payload or "setup_complete" in payload:
            return ProviderEvent(type="status", status="listening")
        if "goAway" in payload or "go_away" in payload:
            return ProviderEvent(
                type="error",
                code="PROVIDER_GOAWAY",
                message=str(payload.get("goAway") or payload.get("go_away")),
            )
        if "serverContent" in payload:
            return self._map_server_content(payload["serverContent"])
        if "server_content" in payload:
            return self._map_server_content(payload["server_content"])
        if "error" in payload:
            error = payload["error"]
            error_payload = error if isinstance(error, dict) else payload
            return ProviderEvent(
                type="error",
                code=str(error_payload.get("code", "PROVIDER_PROTOCOL_ERROR")),
                message=str(error_payload.get("message", "Provider error")),
            )
        return None

    def _map_server_content(self, content: object) -> ProviderEvent | None:
        if not isinstance(content, dict):
            return None
        response_id = str(content.get("responseId") or content.get("response_id") or "")
        if response_id:
            self._current_response_id = response_id
        message_id = response_id or self._current_response_id
        if content.get("generationComplete") or content.get("generation_complete"):
            self._audio_started = False
            return ProviderEvent(type="response_done", message_id=message_id)
        input_text = transcription_text(content.get("inputTranscription")) or transcription_text(
            content.get("input_transcription")
        )
        if input_text:
            return ProviderEvent(
                type="transcript_done",
                speaker="user",
                text=input_text,
                message_id=f"user-{message_id}",
            )
        output_text = transcription_text(content.get("outputTranscription")) or transcription_text(
            content.get("output_transcription")
        )
        if output_text:
            return ProviderEvent(
                type="transcript_delta",
                speaker="assistant",
                text=output_text,
                message_id=message_id,
            )
        audio = model_turn_audio(content.get("modelTurn")) or model_turn_audio(
            content.get("model_turn")
        )
        if audio:
            return ProviderEvent(
                type="audio_delta",
                audio=audio,
                mime_type="audio/pcm;rate=24000",
                message_id=message_id,
            )
        return None


def live_url_with_key(base_url: str, api_key: str) -> str:
    """Return a Gemini Live URL with API key query parameter."""
    parts = urlsplit(base_url or DEFAULT_LIVE_URL)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["key"] = api_key
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def normalize_model_name(model: str) -> str:
    """Gemini Live setup accepts model names with a models/ prefix."""
    resolved = model or DEFAULT_LIVE_MODEL
    return resolved if resolved.startswith("models/") else f"models/{resolved}"


def transcription_text(value: object) -> str:
    """Extract transcript text from camelCase or snake_case Gemini payloads."""
    if not isinstance(value, dict):
        return ""
    return str(value.get("text", ""))


def model_turn_audio(value: object) -> bytes:
    """Extract inline audio bytes from a Gemini model turn."""
    if not isinstance(value, dict):
        return b""
    parts = value.get("parts")
    if not isinstance(parts, list):
        return b""
    for part in parts:
        if not isinstance(part, dict):
            continue
        inline_data = part.get("inlineData") or part.get("inline_data")
        if not isinstance(inline_data, dict):
            continue
        mime_type = str(inline_data.get("mimeType") or inline_data.get("mime_type") or "")
        if not mime_type.startswith("audio/"):
            continue
        encoded = str(inline_data.get("data", ""))
        return base64.b64decode(encoded) if encoded else b""
    return b""


def provider_unavailable_message(exc: Exception) -> str:
    """Build a stable error message for provider connection failures."""
    detail = str(exc).strip() or exc.__class__.__name__
    return f"Gemini live provider unavailable: {detail}"
