from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any, Literal

from sighttalk_api.agent.context import AgentSessionContext
from sighttalk_api.agent.execution import LiveKitExecution
from sighttalk_api.agent.tooling import AgentTooling
from sighttalk_api.providers.base import ImageFrame

LifecycleState = Literal["created", "connecting", "listening", "interrupted", "error", "ended"]


class AgentLifecycle:
    def __init__(
        self,
        *,
        context: AgentSessionContext,
        tooling: AgentTooling,
        execution: LiveKitExecution | None = None,
    ) -> None:
        self.context = context
        self.tooling = tooling
        self.execution = execution
        self.state: LifecycleState = "created"
        self._stopped = asyncio.Event()
        self._tasks: set[asyncio.Task[None]] = set()
        self._provider_ready = asyncio.Event()
        self._provider_audio_started = asyncio.Event()
        self._terminal_error_sent = False
        self._stopping = False

    def set_execution(self, execution: LiveKitExecution) -> None:
        self.execution = execution

    async def run(self) -> None:
        if self.execution is None:
            raise RuntimeError("Agent lifecycle requires an execution harness")
        try:
            self.state = "connecting"
            await self.execution.connect()
            await self.publish_event(self.context.status_event("connecting"))
            await self.execution.publish_assistant_audio_track()
            try:
                await self.tooling.connect()
            except RuntimeError as exc:
                await self._handle_terminal_error("PROVIDER_UNAVAILABLE", str(exc))
                return
            self._provider_ready.set()
            self.state = "listening"
            await self.publish_event(self.context.status_event("listening"))
            provider_task = asyncio.create_task(self._pump_provider_events())
            self._track_task(provider_task)
            await self._stopped.wait()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.publish_event(
                self.context.error_event("AGENT_RUNTIME_ERROR", str(exc))
            )
        finally:
            await self.stop()

    async def stop(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        self._stopped.set()
        for task in list(self._tasks):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self.context.flush_memory()
        await self.tooling.close()
        if self.execution is not None:
            await self.execution.stop()
        if self.state != "error":
            self.state = "ended"

    async def handle_audio_chunk(self, data: bytes, *, sample_rate: int) -> None:
        await self._provider_ready.wait()
        try:
            await self.tooling.send_audio(data, sample_rate=sample_rate)
            self._provider_audio_started.set()
        except RuntimeError as exc:
            await self._handle_terminal_error("PROVIDER_UNAVAILABLE", str(exc))

    async def handle_image_frame(self, frame: ImageFrame) -> None:
        await self._provider_ready.wait()
        await self._provider_audio_started.wait()
        try:
            if await self.tooling.send_image(frame):
                await self.publish_event(self.context.cost_event())
        except RuntimeError as exc:
            await self._handle_terminal_error("PROVIDER_UNAVAILABLE", str(exc))

    async def handle_control_message(self, data: bytes) -> None:
        if self.execution is not None and is_interrupt_message(data):
            await self.execution.interrupt_playback()
            self.state = "interrupted"
            await self.publish_event(self.context.status_event("interrupted"))
        try:
            event = await self.tooling.handle_control_message(data)
        except RuntimeError as exc:
            await self._handle_terminal_error("PROVIDER_UNAVAILABLE", str(exc))
            return
        if event is not None:
            if event.get("type") == "agent.status":
                status = str(event.get("status", "listening"))
                self.state = "listening" if status == "listening" else self.state
            await self.publish_event(event)

    async def publish_event(self, payload: dict[str, Any]) -> None:
        if self.execution is not None:
            await self.execution.publish_event(payload)

    async def _pump_provider_events(self) -> None:
        try:
            async for event in self.tooling.events():
                if self.execution is not None and event.type == "audio_delta" and event.audio:
                    await self.execution.play_assistant_audio(event.audio)
                payload = await self.tooling.handle_provider_event(event)
                if payload is not None:
                    await self.publish_event(payload)
        except asyncio.CancelledError:
            raise
        except RuntimeError as exc:
            await self._handle_terminal_error("PROVIDER_UNAVAILABLE", str(exc))

    async def _handle_terminal_error(self, code: str, message: str) -> None:
        self.state = "error"
        if not self._terminal_error_sent:
            self._terminal_error_sent = True
            await self.publish_event(self.context.error_event(code, message))
        self._stopped.set()

    def _track_task(self, task: asyncio.Task[None]) -> None:
        self._tasks.add(task)
        task.add_done_callback(lambda completed: self._tasks.discard(task))


def is_interrupt_message(data: bytes) -> bool:
    try:
        payload = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return str(payload.get("type", "")) == "client.interrupt"
