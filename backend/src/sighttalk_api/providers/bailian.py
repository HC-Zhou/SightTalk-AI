from __future__ import annotations

import asyncio
import base64
import json
import uuid
from collections.abc import AsyncIterator
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
    ProviderEvent,
    ProviderSessionConfig,
)

DEFAULT_REALTIME_MODEL = "qwen3-omni-flash-realtime"
LEGACY_REALTIME_MODEL = "multimodal-dialog"


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
    ) -> None:
        self._api_key = api_key
        self._realtime_url = normalize_realtime_url(realtime_url)
        self._region = region
        self._workspace_id = workspace_id
        self._model = normalize_realtime_model(model)
        self._connection: ClientConnection | None = None
        self._closed = False

    async def connect(self, session: ProviderSessionConfig) -> None:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }
        if self._workspace_id:
            headers["X-DashScope-WorkSpace"] = self._workspace_id
        try:
            self._connection = await websockets.connect(
                realtime_url_with_model(self._realtime_url, session.model or self._model),
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
            )
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
                            "silence_duration_ms": 800,
                            "create_response": True,
                            "interrupt_response": True,
                        },
                    },
                }
            )
        except Exception as exc:
            raise RuntimeError("PROVIDER_UNAVAILABLE") from exc

    async def send_audio(self, chunk: AudioChunk) -> None:
        await self._send_json(
            {
                "event_id": new_event_id(),
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(chunk.data).decode("ascii"),
            }
        )

    async def send_image(self, frame: ImageFrame) -> None:
        await self._send_json(
            {
                "event_id": new_event_id(),
                "type": "input_image_buffer.append",
                "image": base64.b64encode(frame.data).decode("ascii"),
            }
        )

    async def send_control(self, event: ControlEvent) -> None:
        if event.type == "interrupt":
            await self._send_json({"event_id": new_event_id(), "type": "response.cancel"})

    async def events(self) -> AsyncIterator[ProviderEvent]:
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
        self._closed = True
        if self._connection is not None:
            await self._connection.close()

    async def _send_json(self, payload: dict[str, Any]) -> None:
        if self._connection is None:
            raise RuntimeError("PROVIDER_UNAVAILABLE")
        try:
            await self._connection.send(json.dumps(payload))
        except ConnectionClosed as exc:
            self._connection = None
            raise RuntimeError("PROVIDER_UNAVAILABLE") from exc

    def _map_event(self, payload: dict[str, Any]) -> ProviderEvent | None:
        event_type = str(payload.get("type", ""))
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
            "response.audio_transcript.done",
        }:
            return ProviderEvent(
                type="transcript_delta",
                speaker="assistant",
                text=text or str(payload.get("delta", "")) or str(payload.get("transcript", "")),
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
            return ProviderEvent(
                type="error",
                code=str(error_payload.get("code", "PROVIDER_PROTOCOL_ERROR")),
                message=str(error_payload.get("message", "Provider error")),
            )
        return None


def realtime_url_with_model(base_url: str, model: str) -> str:
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["model"] = normalize_realtime_model(model)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def new_event_id() -> str:
    return f"event_{uuid.uuid4().hex}"


def normalize_realtime_url(url: str) -> str:
    if url.endswith("/inference"):
        return f"{url.removesuffix('/inference')}/realtime"
    return url


def normalize_realtime_model(model: str) -> str:
    if not model or model == LEGACY_REALTIME_MODEL:
        return DEFAULT_REALTIME_MODEL
    return model
