from __future__ import annotations

import asyncio
from contextlib import suppress

from sighttalk_api.agent.context import AgentSessionContext
from sighttalk_api.agent.execution import (
    LiveKitExecution,
    encode_jpeg_under_limit,
    encode_video_frame,
)
from sighttalk_api.agent.lifecycle import AgentLifecycle
from sighttalk_api.agent.tooling import AgentTooling
from sighttalk_api.core.config import Settings
from sighttalk_api.providers.factory import create_provider
from sighttalk_api.schemas.livekit import MediaPolicy
from sighttalk_api.services.memory import MemoryStore

__all__ = [
    "LiveKitAgentManager",
    "LiveKitRoomAgent",
    "encode_jpeg_under_limit",
    "encode_video_frame",
]


class LiveKitRoomAgent:
    def __init__(
        self,
        *,
        room_name: str,
        livekit_url: str,
        assistant_token: str,
        settings: Settings,
        media_policy: MediaPolicy,
        user_id: str = "anonymous",
    ) -> None:
        memory_store = MemoryStore(settings.sighttalk_data_dir)
        self._context = AgentSessionContext(
            session_id=room_name,
            user_id=user_id,
            media_policy=media_policy,
            memory_store=memory_store,
            memory_max_items=settings.harness_memory_max_items,
        )
        self._tooling = AgentTooling(
            provider=create_provider(settings),
            context=self._context,
            settings=settings,
        )
        self._lifecycle = AgentLifecycle(
            context=self._context,
            tooling=self._tooling,
        )
        self._execution = LiveKitExecution(
            room_name=room_name,
            livekit_url=livekit_url,
            assistant_token=assistant_token,
            media_policy=lambda: self._context.media_policy,
            on_audio_chunk=self._lifecycle.handle_audio_chunk,
            on_image_frame=self._lifecycle.handle_image_frame,
            on_control_message=self._lifecycle.handle_control_message,
        )
        self._lifecycle.set_execution(self._execution)

    async def run(self) -> None:
        await self._lifecycle.run()

    async def stop(self) -> None:
        await self._lifecycle.stop()


class LiveKitAgentManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def start(
        self,
        *,
        room_name: str,
        livekit_url: str,
        assistant_token: str,
        settings: Settings,
        media_policy: MediaPolicy,
        user_id: str,
    ) -> None:
        existing = self._tasks.get(room_name)
        if existing is not None and not existing.done():
            return
        agent = LiveKitRoomAgent(
            room_name=room_name,
            livekit_url=livekit_url,
            assistant_token=assistant_token,
            settings=settings,
            media_policy=media_policy,
            user_id=user_id,
        )
        task = asyncio.create_task(agent.run())
        self._tasks[room_name] = task
        task.add_done_callback(lambda completed: self._tasks.pop(room_name, None))

    async def stop(self, room_name: str) -> None:
        task = self._tasks.pop(room_name, None)
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


_agent_manager = LiveKitAgentManager()


def get_agent_manager() -> LiveKitAgentManager:
    return _agent_manager
