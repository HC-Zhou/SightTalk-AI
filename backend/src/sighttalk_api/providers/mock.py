from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from sighttalk_api.providers.base import (
    AIProvider,
    AudioChunk,
    ControlEvent,
    ImageFrame,
    ProviderEvent,
    ProviderSessionConfig,
)


class MockRealtimeProvider(AIProvider):
    def __init__(self) -> None:
        self._queue: asyncio.Queue[ProviderEvent] = asyncio.Queue()
        self._closed = False

    async def connect(self, session: ProviderSessionConfig) -> None:
        await self._queue.put(ProviderEvent(type="status", status="listening"))

    async def send_audio(self, chunk: AudioChunk) -> None:
        if self._closed:
            return
        await self._queue.put(
            ProviderEvent(
                type="transcript_done",
                speaker="user",
                text="Mock audio received.",
                message_id="mock-user",
            )
        )
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

    async def send_image(self, frame: ImageFrame) -> None:
        return

    async def send_control(self, event: ControlEvent) -> None:
        if event.type == "interrupt":
            await self._queue.put(ProviderEvent(type="status", status="interrupted"))
            await self._queue.put(ProviderEvent(type="status", status="listening"))

    async def events(self) -> AsyncIterator[ProviderEvent]:
        while not self._closed:
            yield await self._queue.get()

    async def close(self) -> None:
        self._closed = True
