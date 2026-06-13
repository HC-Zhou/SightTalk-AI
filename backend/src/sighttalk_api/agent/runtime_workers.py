"""Worker implementations used by the agent runtime assembly."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from sighttalk_api.agent.bus import BaseWorker
from sighttalk_api.agent.frames import Frame
from sighttalk_api.agent.short_term_context import (
    ContextBuilder,
    ContextSummarizer,
    ConversationTurn,
    MemoryContextItem,
    ShortTermContext,
    Speaker,
)
from sighttalk_api.providers.base import ProviderContext
from sighttalk_api.services.long_term_memory import (
    LongTermMemory,
    MemoryMessage,
    MemoryScope,
)


@dataclass(frozen=True)
class WorkerJobRequest:
    """A typed request for specialist-worker jobs."""

    job_id: str
    job_type: str
    payload: Mapping[str, Any]
    timeout_seconds: float = 5.0


@dataclass(frozen=True)
class WorkerHandoffRequest:
    """A typed handoff request between agent workers."""

    handoff_id: str
    target_worker_id: str
    reason: str
    payload: Mapping[str, Any]


class ContextWorker(BaseWorker):
    """Owns short-term transcript state, summary state, and prompt construction."""

    def __init__(
        self,
        *,
        context: ShortTermContext,
        builder: ContextBuilder | None = None,
        summarizer: ContextSummarizer | None = None,
        worker_id: str = "context",
    ) -> None:
        super().__init__(
            worker_id=worker_id,
            subscriptions={
                "transcript.delta",
                "transcript.done",
                "context.build",
                "context.summarize",
            },
        )
        self.context = context
        self._builder = builder or ContextBuilder()
        self._summarizer = summarizer or ContextSummarizer(
            recent_turns=context.recent_turns,
        )

    def record_transcript(
        self,
        *,
        speaker: str,
        text: str,
        message_id: str,
        final: bool,
    ) -> ConversationTurn | None:
        """Record transcript text in short-term state."""
        if speaker not in ("user", "assistant"):
            return None
        return self.context.record_transcript(
            speaker=cast(Speaker, speaker),
            text=text,
            message_id=message_id,
            final=final,
        )

    def build_prompt(self, *, memories: Sequence[MemoryContextItem] = ()) -> str:
        """Build provider context from short-term state and retrieved memory."""
        return self._builder.build_prompt(self.context, memories=memories)

    async def summarize_if_needed(self) -> bool:
        """Summarize context if configured limits are exceeded."""
        if not self.context.needs_summarization():
            return False
        result = await self._summarizer.summarize(self.context)
        self.context.apply_summary(result)
        return True

    async def handle_frame(self, frame: Frame) -> Sequence[Frame]:
        """Process transcript/context frames for bus-based runtime paths."""
        if frame.type in {"transcript.delta", "transcript.done"}:
            self.record_transcript(
                speaker=str(frame.payload.get("speaker", "")),
                text=str(frame.payload.get("text", "")),
                message_id=str(frame.payload.get("message_id", "")),
                final=frame.type == "transcript.done",
            )
            return ()
        if frame.type == "context.summarize":
            await self.summarize_if_needed()
            return ()
        if frame.type == "context.build":
            memories = [
                MemoryContextItem(text=str(item))
                for item in frame.payload.get("memories", [])
                if str(item).strip()
            ]
            return [
                Frame.data(
                    "context.updated",
                    payload={"system_prompt": self.build_prompt(memories=memories)},
                    source=self.worker_id,
                    target=str(frame.payload.get("reply_to") or ""),
                    interruptible=False,
                )
            ]
        return ()


class MemoryWorker(BaseWorker):
    """Owns long-term memory search/add with non-fatal failure semantics."""

    def __init__(
        self,
        *,
        memory: LongTermMemory,
        scope: MemoryScope,
        search_limit: int,
        search_threshold: float,
        worker_id: str = "memory",
    ) -> None:
        super().__init__(
            worker_id=worker_id,
            subscriptions={"memory.search", "memory.add_turn"},
        )
        self.memory = memory
        self.scope = scope
        self.search_limit = search_limit
        self.search_threshold = search_threshold
        self.last_error: str | None = None

    async def search(self, query: str) -> list[MemoryContextItem]:
        """Search long-term memory and convert failures to empty results."""
        try:
            results = await self.memory.search(
                self.scope,
                query,
                limit=self.search_limit,
                threshold=self.search_threshold,
            )
        except Exception as exc:
            self.last_error = str(exc)
            return []
        return [MemoryContextItem(text=result.text, score=result.score) for result in results]

    async def add_finalized_turns(self, turns: Sequence[ConversationTurn]) -> int:
        """Persist finalized text turns one at a time with SightTalk metadata."""
        written = 0
        for turn in turns:
            text = turn.text.strip()
            if not text:
                continue
            metadata = {
                "session_id": self.scope.run_id,
                "turn_id": turn.turn_id,
                "media_mode": turn.media_mode,
                "has_visual_context": turn.has_visual_context,
                "source": "sighttalk_realtime",
            }
            try:
                await self.memory.add_turn(
                    self.scope,
                    [MemoryMessage(role=turn.speaker, content=text)],
                    metadata,
                )
            except Exception as exc:
                self.last_error = str(exc)
                continue
            written += 1
        return written

    async def handle_frame(self, frame: Frame) -> Sequence[Frame]:
        """Process long-term memory frames."""
        if frame.type == "memory.search":
            query = str(frame.payload.get("query", ""))
            results = await self.search(query)
            reply_to = frame.payload.get("reply_to")
            if not reply_to:
                return ()
            return [
                Frame.data(
                    "memory.search.result",
                    payload={"memories": [result.text for result in results]},
                    source=self.worker_id,
                    target=str(reply_to),
                )
            ]
        return ()

    async def stop(self) -> None:
        """Close the long-term memory backend during worker shutdown."""
        await self.memory.close()
        await super().stop()


class TransportWorker(BaseWorker):
    """Worker wrapper for LiveKit execution responsibilities."""

    def __init__(self, *, execution: Any, worker_id: str = "transport") -> None:
        super().__init__(
            worker_id=worker_id,
            subscriptions={"transport.publish", "transport.interrupt"},
        )
        self.execution = execution

    async def handle_frame(self, frame: Frame) -> Sequence[Frame]:
        if frame.type == "transport.publish":
            await self.execution.publish_event(dict(frame.payload))
        elif frame.type == "transport.interrupt":
            await self.execution.interrupt_playback()
        return ()


class ProviderWorker(BaseWorker):
    """Worker wrapper for provider/tooling responsibilities."""

    def __init__(self, *, tooling: Any, worker_id: str = "provider") -> None:
        super().__init__(
            worker_id=worker_id,
            subscriptions={"provider.context_update", "provider.response.create"},
        )
        self.tooling = tooling

    async def handle_frame(self, frame: Frame) -> Sequence[Frame]:
        if frame.type == "provider.context_update":
            await self.tooling.provider.update_context(
                ProviderContext(system_prompt=str(frame.payload.get("system_prompt", "")))
            )
        elif frame.type == "provider.response.create":
            await self.tooling.provider.create_response()
        return ()


class MainAgentWorker(BaseWorker):
    """Worker wrapper for main lifecycle coordination."""

    def __init__(self, *, lifecycle: Any, worker_id: str = "main") -> None:
        super().__init__(
            worker_id=worker_id,
            subscriptions={"agent.interrupt", "agent.terminal_error"},
        )
        self.lifecycle = lifecycle

    async def handle_frame(self, frame: Frame) -> Sequence[Frame]:
        if frame.type == "agent.interrupt":
            await self.lifecycle.handle_control_message(b'{"type":"client.interrupt"}')
        elif frame.type == "agent.terminal_error":
            await self.lifecycle._handle_terminal_error(  # noqa: SLF001
                str(frame.payload.get("code", "AGENT_RUNTIME_ERROR")),
                str(frame.payload.get("message", "Agent runtime error")),
            )
        return ()


class JobCoordinator:
    """Small in-process job API for future specialist workers."""

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[Frame]] = {}

    def create_job_frame(
        self,
        request: WorkerJobRequest,
        *,
        source: str,
        target: str,
    ) -> Frame:
        """Create a targeted job request frame and register its completion future."""
        loop = asyncio.get_running_loop()
        self._pending[request.job_id] = loop.create_future()
        return Frame.data(
            "job.request",
            payload={
                "job_id": request.job_id,
                "job_type": request.job_type,
                "payload": dict(request.payload),
                "timeout_seconds": request.timeout_seconds,
            },
            source=source,
            target=target,
        )

    def create_handoff_frame(self, request: WorkerHandoffRequest, *, source: str) -> Frame:
        """Create a targeted handoff request frame."""
        return Frame.control(
            "handoff.request",
            payload={
                "handoff_id": request.handoff_id,
                "reason": request.reason,
                "payload": dict(request.payload),
            },
            source=source,
            target=request.target_worker_id,
        )

    def complete(self, frame: Frame) -> bool:
        """Complete a pending job from `job.result` or `job.error` frame."""
        job_id = str(frame.payload.get("job_id", ""))
        future = self._pending.get(job_id)
        if future is None or future.done():
            return False
        future.set_result(frame)
        return True

    async def wait_for_job(self, job_id: str, *, timeout_seconds: float) -> Frame:
        """Wait for a job result frame with timeout cleanup."""
        future = self._pending.get(job_id)
        if future is None:
            raise KeyError(job_id)
        try:
            return await asyncio.wait_for(future, timeout=timeout_seconds)
        finally:
            self._pending.pop(job_id, None)
