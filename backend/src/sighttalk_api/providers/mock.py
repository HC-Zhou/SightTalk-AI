"""Deterministic in-process provider for local demos and automated tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

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


class MockRealtimeProvider(AIProvider):
    """Queue-backed provider that simulates a short realtime conversation."""

    def __init__(self, *, manual_response_enabled: bool = False) -> None:
        self._queue: asyncio.Queue[ProviderEvent] = asyncio.Queue()
        self._closed = False
        self._manual_response_enabled = manual_response_enabled
        self._context: ProviderContext | None = None
        self.calls: list[str] = []

    def capabilities(self) -> ProviderCapabilities:
        """Expose manual response support only when enabled."""
        return ProviderCapabilities(
            supports_manual_response=self._manual_response_enabled,
            supports_context_update=self._manual_response_enabled,
        )

    async def connect(self, session: ProviderSessionConfig) -> None:
        """Mark the mock provider as ready to listen."""
        await self._queue.put(ProviderEvent(type="status", status="listening"))

    async def update_context(self, context: ProviderContext) -> None:
        """Store context updates for tests and manual response flow."""
        self.calls.append("update_context")
        self._context = context

    async def create_response(self) -> None:
        """Emit the deterministic assistant response in manual response mode."""
        self.calls.append("create_response")
        if not self._manual_response_enabled or self._closed:
            return
        await self._emit_assistant_response()

    async def send_audio(self, chunk: AudioChunk) -> None:
        """Emit a deterministic transcript/response sequence for any audio chunk."""
        if self._closed:
            return
        self.calls.append("send_audio")
        await self._queue.put(
            ProviderEvent(
                type="transcript_done",
                speaker="user",
                text="Mock audio received.",
                message_id="mock-user",
            )
        )
        if self._manual_response_enabled:
            return
        await self._emit_assistant_response()

    async def _emit_assistant_response(self) -> None:
        """Emit the deterministic assistant response sequence."""
        await self._queue.put(ProviderEvent(type="status", status="thinking"))
        await self._queue.put(
            ProviderEvent(
                type="transcript_delta",
                speaker="assistant",
                text="I can hear you and I am ready to inspect the camera view.",
                message_id="mock-assistant",
            )
        )
        await self._queue.put(
            ProviderEvent(
                type="transcript_done",
                speaker="assistant",
                text="I can hear you and I am ready to inspect the camera view.",
                message_id="mock-assistant",
            )
        )
        await self._queue.put(ProviderEvent(type="response_done", message_id="mock-assistant"))
        await self._queue.put(ProviderEvent(type="status", status="listening"))

    async def send_image(self, frame: ImageFrame) -> bool:
        """Accept image frames without emitting extra events."""
        return True

    async def send_control(self, event: ControlEvent) -> None:
        """Simulate provider interruption handling."""
        if event.type == "interrupt":
            await self._queue.put(ProviderEvent(type="status", status="interrupted"))
            await self._queue.put(ProviderEvent(type="status", status="listening"))

    async def events(self) -> AsyncIterator[ProviderEvent]:
        """Yield queued mock events until the provider closes."""
        while not self._closed:
            yield await self._queue.get()

    async def close(self) -> None:
        """Stop the mock event stream."""
        self._closed = True
