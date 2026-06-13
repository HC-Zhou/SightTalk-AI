from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from typing import Any, cast

from sighttalk_api.agent.context import AgentSessionContext, utc_now
from sighttalk_api.agent.media_policy import derive_mode_policy
from sighttalk_api.core.config import Settings
from sighttalk_api.providers.base import (
    AIProvider,
    AudioChunk,
    ControlEvent,
    ImageFrame,
    ProviderEvent,
    ProviderSessionConfig,
)
from sighttalk_api.schemas.livekit import MediaMode


class AgentTooling:
    def __init__(
        self,
        *,
        provider: AIProvider,
        context: AgentSessionContext,
        settings: Settings,
    ) -> None:
        self.provider = provider
        self.context = context
        self.settings = settings
        self._audio_started = False

    @property
    def audio_started(self) -> bool:
        return self._audio_started

    async def connect(self) -> None:
        await self.provider.connect(
            ProviderSessionConfig(
                session_id=self.context.session_id,
                model=self.settings.bailian_model,
                workspace_id=self.settings.bailian_workspace_id,
                system_prompt=self.context.build_system_prompt(),
            )
        )

    async def send_audio(self, data: bytes, *, sample_rate: int = 16_000) -> None:
        await self.provider.send_audio(AudioChunk(data=data, sample_rate=sample_rate))
        self.context.add_audio(data, sample_rate=sample_rate)
        self._audio_started = True

    async def send_image(self, frame: ImageFrame) -> bool:
        if not self._audio_started:
            return False
        await self.provider.send_image(frame)
        self.context.add_image_frame()
        return True

    async def handle_control_message(self, raw: str | bytes) -> dict[str, Any] | None:
        try:
            payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except json.JSONDecodeError:
            return self.context.error_event("MALFORMED_CONTROL_EVENT", "Malformed control event")

        event_type = payload.get("type")
        if event_type == "client.mode.update":
            raw_mode = payload.get("mode")
            if raw_mode in ("economy", "balanced", "accurate"):
                mode = cast(MediaMode, raw_mode)
                self.context.media_policy = derive_mode_policy(self.context.media_policy, mode)
                await self.provider.send_control(ControlEvent(type="mode_update", value=mode))
                return self.context.cost_event()
            return self.context.error_event("INVALID_MEDIA_MODE", "Unsupported media mode")
        if event_type == "client.interrupt":
            await self.provider.send_control(ControlEvent(type="interrupt"))
            return self.context.status_event("listening")
        return None

    async def handle_provider_event(self, event: ProviderEvent) -> dict[str, Any] | None:
        payload = self.map_provider_event(event)
        if event.type == "response_done":
            self.context.flush_memory()
        return payload

    def map_provider_event(self, event: ProviderEvent) -> dict[str, Any] | None:
        base: dict[str, Any] = {
            "session_id": self.context.session_id,
            "timestamp": utc_now(),
        }
        if event.type == "status":
            return {**base, "type": "agent.status", "status": event.status}
        if event.type == "transcript_delta":
            self.context.record_transcript(
                speaker=event.speaker,
                text=event.text,
                message_id=event.message_id,
                final=False,
            )
            return {
                **base,
                "type": "transcript.delta",
                "speaker": event.speaker,
                "text": event.text,
                "message_id": event.message_id,
            }
        if event.type == "transcript_done":
            self.context.record_transcript(
                speaker=event.speaker,
                text=event.text,
                message_id=event.message_id,
                final=True,
            )
            return {
                **base,
                "type": "transcript.done",
                "speaker": event.speaker,
                "text": event.text,
                "message_id": event.message_id,
            }
        if event.type == "response_done":
            return {
                **base,
                "type": "response.done",
                "message_id": event.message_id,
                "audio_playback_complete": False,
            }
        if event.type == "audio_delta":
            return {
                **base,
                "type": "audio.delta",
                "message_id": event.message_id,
                "mime_type": event.mime_type,
                "audio": base64.b64encode(event.audio).decode("ascii"),
            }
        if event.type == "error":
            return {**base, "type": "error", "code": event.code, "message": event.message}
        return None

    def events(self) -> AsyncIterator[ProviderEvent]:
        return self.provider.events()

    async def close(self) -> None:
        await self.provider.close()
