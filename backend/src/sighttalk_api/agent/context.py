"""Conversation context, memory hydration, and event payload helpers for agents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sighttalk_api.agent.prompts import BASE_SYSTEM_PROMPT
from sighttalk_api.agent.runtime_workers import ContextWorker, MemoryWorker
from sighttalk_api.agent.short_term_context import (
    ContextBuilder,
    MemoryContextItem,
    SessionState,
    ShortTermContext,
)
from sighttalk_api.schemas.livekit import MediaPolicy
from sighttalk_api.services.long_term_memory import (
    DisabledLongTermMemory,
    LocalJsonlLongTermMemory,
    LongTermMemory,
    MemoryScope,
)
from sighttalk_api.services.memory import MemoryStore, memory_record_now


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp for LiveKit data-message payloads."""
    return datetime.now(tz=UTC).isoformat()


@dataclass
class TranscriptMessage:
    """Normalized transcript message retained until it is safe to persist."""

    message_id: str
    speaker: Literal["user", "assistant"]
    text: str
    final: bool


class AgentSessionContext:
    """Mutable per-room state shared by realtime execution and provider tooling.

    The context intentionally owns only business state: media policy, usage counters,
    transcript aggregation, memory hydration, and normalized outbound events. Transport
    concerns remain in the LiveKit execution layer.
    """

    def __init__(
        self,
        *,
        session_id: str,
        user_id: str,
        media_policy: MediaPolicy,
        memory_store: MemoryStore | None = None,
        memory_max_items: int = 20,
        short_memory_max_messages: int = 24,
        short_memory_max_estimated_tokens: int = 8000,
        memory_search_limit: int = 5,
        memory_search_threshold: float = 0.3,
        memory_agent_id: str = "sighttalk",
        long_term_memory: LongTermMemory | None = None,
    ) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.media_policy = media_policy
        self.memory_store = memory_store
        self.memory_max_items = memory_max_items
        self.audio_seconds = 0.0
        self.image_frames_sent = 0
        self._messages: dict[str, TranscriptMessage] = {}
        self._flushed_message_ids: set[str] = set()
        self._flushed_turn_ids: set[str] = set()
        self._short_context = ShortTermContext(
            state=SessionState(
                session_id=session_id,
                user_id=user_id,
                media_policy=media_policy,
            ),
            max_messages=short_memory_max_messages,
            max_estimated_tokens=short_memory_max_estimated_tokens,
        )
        self.context_worker = ContextWorker(
            context=self._short_context,
            builder=ContextBuilder(base_prompt=BASE_SYSTEM_PROMPT),
        )
        resolved_long_term_memory = long_term_memory or (
            LocalJsonlLongTermMemory(memory_store)
            if memory_store is not None
            else DisabledLongTermMemory()
        )
        self.memory_worker = MemoryWorker(
            memory=resolved_long_term_memory,
            scope=MemoryScope(
                user_id=user_id,
                agent_id=memory_agent_id,
                run_id=session_id,
            ),
            search_limit=memory_search_limit,
            search_threshold=memory_search_threshold,
        )

    def build_system_prompt(self) -> str:
        """Build the provider system prompt with bounded user memory context."""
        return self.context_worker.build_prompt(memories=self._recent_memory_items_sync())

    async def build_system_prompt_async(self, *, search_query: str = "") -> str:
        """Build provider prompt through ContextWorker and MemoryWorker."""
        await self._consolidate_short_context_if_needed()
        memories = await self.memory_worker.search(search_query)
        return self.context_worker.build_prompt(memories=memories)

    def _recent_memory_items_sync(self) -> list[MemoryContextItem]:
        """Hydrate local JSONL memories for synchronous compatibility callers."""
        if self.memory_store is None:
            return []
        records = self.memory_store.recent(
            user_id=self.user_id,
            limit=self.memory_max_items,
        )
        return [
            MemoryContextItem(
                text=f"{record.timestamp.isoformat()} {record.speaker}: {record.text.strip()}"
            )
            for record in records
            if record.text.strip()
        ]

    def add_audio(self, data: bytes, *, sample_rate: int) -> None:
        """Accumulate billable audio duration based on 16-bit PCM samples."""
        self.audio_seconds += len(data) / max(sample_rate * 2, 1)
        self._short_context.add_audio(data, sample_rate=sample_rate)

    def add_image_frame(self) -> None:
        """Record that one encoded camera frame was sent to the provider."""
        self.image_frames_sent += 1
        self._short_context.state.media_policy = self.media_policy
        self._short_context.add_image_frame()

    def record_transcript(
        self,
        *,
        speaker: Literal["user", "assistant"],
        text: str,
        message_id: str,
        final: bool,
    ) -> None:
        """Merge provider transcript deltas and final messages by message id."""
        resolved_id = message_id or f"{speaker}-{len(self._messages) + 1}"
        existing = self._messages.get(resolved_id)
        next_text = text if final or existing is None else f"{existing.text}{text}"
        self._messages[resolved_id] = TranscriptMessage(
            message_id=resolved_id,
            speaker=speaker,
            text=next_text,
            final=final,
        )
        self._short_context.state.media_policy = self.media_policy
        self.context_worker.record_transcript(
            speaker=speaker,
            text=text,
            message_id=message_id,
            final=final,
        )

    def flush_memory(self) -> int:
        """Synchronously persist finalized turns to the local memory store."""
        if self.memory_store is None:
            return 0
        written = 0
        for turn in self._short_context.finalized_turns:
            if turn.turn_id in self._flushed_turn_ids:
                continue
            text = turn.text.strip()
            if not text:
                continue
            self.memory_store.append(
                memory_record_now(
                    user_id=self.user_id,
                    session_id=self.session_id,
                    speaker=turn.speaker,
                    text=text,
                )
            )
            self._flushed_turn_ids.add(turn.turn_id)
            self._flushed_message_ids.add(turn.message_id)
            written += 1
        return written

    async def flush_memory_async(self) -> int:
        """Persist newly finalized turns through MemoryWorker."""
        pending_turns = [
            turn
            for turn in self._short_context.finalized_turns
            if turn.turn_id not in self._flushed_turn_ids and turn.text.strip()
        ]
        written = await self.memory_worker.add_finalized_turns(pending_turns)
        for turn in pending_turns:
            self._flushed_turn_ids.add(turn.turn_id)
            self._flushed_message_ids.add(turn.message_id)
        await self._consolidate_short_context_if_needed()
        return written

    async def _consolidate_short_context_if_needed(self) -> None:
        """Summarize old short-term turns and persist the summary when supported."""
        result = await self.context_worker.summarize_if_needed()
        if result is None or result.used_fallback:
            return
        if not result.summary.strip() or not result.summarized_turns:
            return
        await self.memory_worker.add_short_term_summary(
            result.summary,
            result.summarized_turns,
        )

    def status_event(self, status: str) -> dict[str, Any]:
        """Create a normalized agent status event for frontend consumers."""
        return {
            "type": "agent.status",
            "session_id": self.session_id,
            "timestamp": utc_now(),
            "status": status,
        }

    def cost_event(self) -> dict[str, Any]:
        """Create a lightweight usage estimate event for the active session."""
        return {
            "type": "cost.estimate",
            "session_id": self.session_id,
            "timestamp": utc_now(),
            "audio_seconds": round(self.audio_seconds, 2),
            "image_frames_sent": self.image_frames_sent,
            "mode": self.media_policy.mode,
        }

    def error_event(self, code: str, message: str) -> dict[str, Any]:
        """Create a frontend-safe error event without provider credentials or internals."""
        return {
            "type": "error",
            "session_id": self.session_id,
            "timestamp": utc_now(),
            "code": code,
            "message": message,
        }
