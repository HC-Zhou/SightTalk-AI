from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from sighttalk_api.providers.base import (
    AIProvider,
    AudioChunk,
    ControlEvent,
    ImageFrame,
    ProviderEvent,
    ProviderSessionConfig,
)


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
        self._realtime_url = realtime_url
        self._region = region
        self._workspace_id = workspace_id
        self._model = model
        self._connection: ClientConnection | None = None
        self._closed = False

    async def connect(self, session: ProviderSessionConfig) -> None:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "X-DashScope-WorkSpace": self._workspace_id,
        }
        try:
            self._connection = await websockets.connect(
                self._realtime_url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
            )
            await self._send_json(
                {
                    "type": "session.create",
                    "session_id": session.session_id,
                    "model": session.model or self._model,
                    "workspace_id": session.workspace_id or self._workspace_id,
                    "region": self._region,
                    "system_prompt": session.system_prompt,
                    "modalities": ["audio", "image", "text"],
                }
            )
        except Exception as exc:
            raise RuntimeError("PROVIDER_UNAVAILABLE") from exc

    async def send_audio(self, chunk: AudioChunk) -> None:
        await self._send_json(
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(chunk.data).decode("ascii"),
                "sample_rate": chunk.sample_rate,
                "mime_type": chunk.mime_type,
            }
        )

    async def send_image(self, frame: ImageFrame) -> None:
        await self._send_json(
            {
                "type": "input_image.append",
                "image": base64.b64encode(frame.data).decode("ascii"),
                "mime_type": frame.mime_type,
                "width": frame.width,
                "height": frame.height,
            }
        )

    async def send_control(self, event: ControlEvent) -> None:
        await self._send_json({"type": f"control.{event.type}", "value": event.value})

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
        await self._connection.send(json.dumps(payload))

    def _map_event(self, payload: dict[str, Any]) -> ProviderEvent | None:
        event_type = str(payload.get("type", ""))
        text = str(payload.get("text", ""))
        message_id = str(payload.get("message_id", ""))

        if event_type in {"transcript.delta", "conversation.item.input_audio_transcription.delta"}:
            return ProviderEvent(
                type="transcript_delta",
                speaker="user",
                text=text or str(payload.get("delta", "")),
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
        if event_type in {"response.text.delta", "response.audio_transcript.delta"}:
            return ProviderEvent(
                type="transcript_delta",
                speaker="assistant",
                text=text or str(payload.get("delta", "")),
                message_id=message_id,
            )
        if event_type in {"response.done", "response.completed"}:
            return ProviderEvent(type="response_done", message_id=message_id)
        if event_type in {"error", "session.error"}:
            return ProviderEvent(
                type="error",
                code=str(payload.get("code", "PROVIDER_PROTOCOL_ERROR")),
                message=str(payload.get("message", "Provider error")),
            )
        return None
