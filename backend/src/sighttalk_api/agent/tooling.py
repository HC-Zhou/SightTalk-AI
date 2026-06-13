"""Provider-facing tooling that maps application events to AI provider contracts."""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any, cast

from sighttalk_api.agent.context import AgentSessionContext, utc_now
from sighttalk_api.agent.media_policy import derive_mode_policy
from sighttalk_api.core.config import Settings
from sighttalk_api.providers.base import (
    AIProvider,
    AudioChunk,
    ControlEvent,
    ImageFrame,
    ProviderContext,
    ProviderEvent,
    ProviderSessionConfig,
)
from sighttalk_api.schemas.livekit import MediaMode


class AgentTooling:
    """Adapts SightTalk session state to the configured AI provider.

    This class is the translation boundary between provider-neutral application
    events and vendor-specific realtime APIs. It also updates context counters and
    transcript memory so transport code does not need provider knowledge.
    """

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
        self._memory_flush_tasks: set[asyncio.Task[int]] = set()

    @property
    def audio_started(self) -> bool:
        """Whether any user audio has been forwarded during this session."""
        return self._audio_started

    async def connect(self) -> None:
        """Open the provider session with the hydrated system prompt."""
        await self.provider.connect(
            ProviderSessionConfig(
                session_id=self.context.session_id,
                model=self.settings.bailian_model,
                workspace_id=self.settings.bailian_workspace_id,
                system_prompt=await self.context.build_system_prompt_async(),
            )
        )

    async def send_audio(self, data: bytes, *, sample_rate: int = 16_000) -> None:
        """Forward microphone audio and update usage accounting."""
        await self.provider.send_audio(AudioChunk(data=data, sample_rate=sample_rate))
        self.context.add_audio(data, sample_rate=sample_rate)
        self._audio_started = True

    async def send_image(self, frame: ImageFrame) -> bool:
        """Forward a camera frame after audio starts, returning whether it was sent."""
        if not self._audio_started:
            return False
        if not await self.provider.send_image(frame):
            return False
        self.context.add_image_frame()
        return True

    async def handle_control_message(self, raw: str | bytes) -> dict[str, Any] | None:
        """Validate frontend control messages and map them to provider controls."""
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
        """Map provider events and flush memory when a response completes."""
        payload = self.map_provider_event(event)
        if event.type == "transcript_done" and event.speaker == "user":
            await self._maybe_create_manual_response(event.text)
        if event.type == "response_done":
            self.schedule_memory_flush()
        return payload

    def schedule_memory_flush(self) -> None:
        """Persist finalized turns outside the realtime provider event path."""
        active_flush = any(not task.done() for task in self._memory_flush_tasks)
        if active_flush:
            return
        task = asyncio.create_task(self.context.flush_memory_async())
        self._memory_flush_tasks.add(task)
        task.add_done_callback(self._discard_memory_flush_task)

    def _discard_memory_flush_task(self, task: asyncio.Task[int]) -> None:
        self._memory_flush_tasks.discard(task)
        with suppress(asyncio.CancelledError, Exception):
            task.result()

    async def _maybe_create_manual_response(self, query: str) -> None:
        """Gate provider response creation on memory retrieval when supported."""
        capabilities = self.provider.capabilities()
        if not (
            capabilities.supports_manual_response
            and capabilities.supports_context_update
        ):
            return
        prompt = await self.context.build_system_prompt_async(search_query=query)
        await self.provider.update_context(ProviderContext(system_prompt=prompt))
        await self.provider.create_response()

    def map_provider_event(self, event: ProviderEvent) -> dict[str, Any] | None:
        """Convert provider-neutral events into the frontend LiveKit JSON contract."""
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
        """Expose the provider event stream to lifecycle orchestration."""
        return self.provider.events()

    async def close(self) -> None:
        """Close the provider session and release network resources."""
        if self._memory_flush_tasks:
            done, pending = await asyncio.wait(self._memory_flush_tasks, timeout=2.0)
            for task in pending:
                task.cancel()
            for task in done:
                with suppress(Exception):
                    task.result()
        await self.provider.close()
