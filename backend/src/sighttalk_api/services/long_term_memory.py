"""Long-term memory protocol and backend adapters."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from sighttalk_api.core.config import Settings
from sighttalk_api.services.memory import MemoryStore, memory_record_now

MemoryRole = Literal["user", "assistant"]
LOCAL_MARKDOWN_MEMORY_MAX_FACTS = 200
LOCAL_MARKDOWN_HISTORY_ENTRY_MAX_CHARS = 1_200
LOCAL_MARKDOWN_FACT_TRIGGERS = (
    "记住",
    "以后",
    "我叫",
    "我的名字",
    "我是",
    "我的",
    "我喜欢",
    "我不喜欢",
    "我偏好",
    "我需要",
    "remember",
    "my name",
    "i am",
    "i'm",
    "my ",
    "i like",
    "i dislike",
    "i prefer",
    "i need",
)


@dataclass(frozen=True)
class MemoryScope:
    """Entity scope for long-term memory isolation and cross-session recall."""

    user_id: str
    agent_id: str
    run_id: str


@dataclass(frozen=True)
class MemoryMessage:
    """One text message passed to long-term memory backends."""

    role: MemoryRole
    content: str


@dataclass(frozen=True)
class MemorySearchResult:
    """Normalized long-term memory search result."""

    text: str
    score: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class LongTermMemory(Protocol):
    """Protocol implemented by all long-term memory backends."""

    async def search(
        self,
        scope: MemoryScope,
        query: str,
        *,
        limit: int,
        threshold: float,
    ) -> list[MemorySearchResult]:
        raise NotImplementedError

    async def add_turn(
        self,
        scope: MemoryScope,
        messages: Sequence[MemoryMessage],
        metadata: Mapping[str, Any],
    ) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class DisabledLongTermMemory:
    """No-op memory backend used when memory is disabled."""

    async def search(
        self,
        scope: MemoryScope,
        query: str,
        *,
        limit: int,
        threshold: float,
    ) -> list[MemorySearchResult]:
        """Return no memories."""
        return []

    async def add_turn(
        self,
        scope: MemoryScope,
        messages: Sequence[MemoryMessage],
        metadata: Mapping[str, Any],
    ) -> None:
        """Ignore memory writes."""
        return

    async def close(self) -> None:
        """No resources to release."""
        return


class LocalJsonlLongTermMemory:
    """Long-term memory adapter backed by the existing local JSONL store."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    async def search(
        self,
        scope: MemoryScope,
        query: str,
        *,
        limit: int,
        threshold: float,
    ) -> list[MemorySearchResult]:
        """Return recent user-scoped JSONL records matching the query text if present."""
        del threshold
        query_terms = [term.lower() for term in query.split() if term.strip()]
        record_limit = limit * 4 if query_terms else limit
        records = self._store.recent(user_id=scope.user_id, limit=record_limit)
        results: list[MemorySearchResult] = []
        for record in reversed(records):
            text = record.text.strip()
            if not text:
                continue
            if query_terms and not any(term in text.lower() for term in query_terms):
                continue
            results.append(
                MemorySearchResult(
                    text=f"{record.speaker}: {text}",
                    metadata={
                        "session_id": record.session_id,
                        "timestamp": record.timestamp.isoformat(),
                    },
                )
            )
            if len(results) >= limit:
                break
        return list(reversed(results))

    async def add_turn(
        self,
        scope: MemoryScope,
        messages: Sequence[MemoryMessage],
        metadata: Mapping[str, Any],
    ) -> None:
        """Append non-empty finalized text messages to the JSONL store."""
        session_id = str(metadata.get("session_id", scope.run_id))
        for message in messages:
            text = message.content.strip()
            if not text:
                continue
            self._store.append(
                memory_record_now(
                    user_id=scope.user_id,
                    session_id=session_id,
                    speaker=message.role,
                    text=text,
                )
            )

    async def close(self) -> None:
        """No resources to release."""
        return


class LocalMarkdownMemory:
    """Local markdown long-term memory.

    Each user gets transparent, inspectable memory files:

    - `MEMORY.md` contains durable facts/preferences that are injected every turn.
    - `HISTORY.md` is an append-only timeline that can be keyword searched.
    """

    def __init__(
        self,
        data_dir: Path,
        *,
        max_memory_facts: int = LOCAL_MARKDOWN_MEMORY_MAX_FACTS,
    ) -> None:
        self._root = data_dir / "markdown_memory"
        self._max_memory_facts = max_memory_facts

    async def search(
        self,
        scope: MemoryScope,
        query: str,
        *,
        limit: int,
        threshold: float,
    ) -> list[MemorySearchResult]:
        """Return MEMORY.md plus grep-like HISTORY.md matches for non-empty queries."""
        del threshold
        return await asyncio.to_thread(
            self._search_sync,
            scope,
            query,
            limit,
        )

    async def add_turn(
        self,
        scope: MemoryScope,
        messages: Sequence[MemoryMessage],
        metadata: Mapping[str, Any],
    ) -> None:
        """Append timeline entries and extract simple durable user facts."""
        await asyncio.to_thread(self._add_turn_sync, scope, messages, metadata)

    async def add_short_term_summary(
        self,
        scope: MemoryScope,
        summary: str,
        metadata: Mapping[str, Any],
    ) -> None:
        """Append a short-term consolidation summary to HISTORY.md."""
        text = compact_memory_text(summary)
        if not text:
            return
        await asyncio.to_thread(
            self._append_history_entry,
            scope,
            text,
            {
                **dict(metadata),
                "speaker": "summary",
                "source": "sighttalk_short_context_consolidation",
            },
        )

    async def close(self) -> None:
        """No resources to release."""
        return

    def _search_sync(
        self,
        scope: MemoryScope,
        query: str,
        limit: int,
    ) -> list[MemorySearchResult]:
        memory_path = self._memory_path(scope)
        history_path = self._history_path(scope)
        results: list[MemorySearchResult] = []

        memory_text = read_markdown_payload(memory_path)
        if memory_text:
            results.append(
                MemorySearchResult(
                    text=f"MEMORY.md:\n{memory_text}",
                    metadata={"source": "MEMORY.md", "path": str(memory_path)},
                )
            )

        query_terms = keyword_terms(query)
        if query_terms and history_path.exists():
            matches = matching_history_entries(history_path, query_terms, limit=limit)
            results.extend(
                MemorySearchResult(
                    text=f"HISTORY.md: {entry}",
                    metadata={"source": "HISTORY.md", "path": str(history_path)},
                )
                for entry in matches
            )
        return results[: max(limit, 1)] if query_terms else results

    def _add_turn_sync(
        self,
        scope: MemoryScope,
        messages: Sequence[MemoryMessage],
        metadata: Mapping[str, Any],
    ) -> None:
        for message in messages:
            text = compact_memory_text(message.content)
            if not text:
                continue
            self._append_history_entry(
                scope,
                text,
                {**dict(metadata), "speaker": message.role},
            )
            if message.role == "user" and should_promote_to_memory(text):
                self._append_memory_fact(scope, text)

    def _append_history_entry(
        self,
        scope: MemoryScope,
        text: str,
        metadata: Mapping[str, Any],
    ) -> None:
        history_path = self._history_path(scope)
        history_path.parent.mkdir(parents=True, exist_ok=True)
        if not history_path.exists():
            history_path.write_text("# HISTORY.md\n\n", encoding="utf-8")
        timestamp = datetime.now(tz=UTC).isoformat()
        speaker = str(metadata.get("speaker", "unknown"))
        session_id = str(metadata.get("session_id", scope.run_id))
        turn_id = str(metadata.get("turn_id", ""))
        source = str(metadata.get("source", "sighttalk_realtime"))
        clipped = text[:LOCAL_MARKDOWN_HISTORY_ENTRY_MAX_CHARS]
        if len(text) > LOCAL_MARKDOWN_HISTORY_ENTRY_MAX_CHARS:
            clipped = f"{clipped}..."
        detail = f"session={session_id}"
        if turn_id:
            detail = f"{detail} turn={turn_id}"
        entry = f"- [{timestamp}] ({source}; {detail}) {speaker}: {clipped}\n"
        with history_path.open("a", encoding="utf-8") as file:
            file.write(entry)

    def _append_memory_fact(self, scope: MemoryScope, text: str) -> None:
        memory_path = self._memory_path(scope)
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        existing_lines = read_memory_fact_lines(memory_path)
        fact = f"- {text}"
        normalized = normalize_fact_line(fact)
        if any(normalize_fact_line(line) == normalized for line in existing_lines):
            return
        next_lines = [*existing_lines, fact][-self._max_memory_facts :]
        content = "# MEMORY.md\n\n" + "\n".join(next_lines).strip() + "\n"
        memory_path.write_text(content, encoding="utf-8")

    def _memory_path(self, scope: MemoryScope) -> Path:
        return self._scope_dir(scope) / "MEMORY.md"

    def _history_path(self, scope: MemoryScope) -> Path:
        return self._scope_dir(scope) / "HISTORY.md"

    def _scope_dir(self, scope: MemoryScope) -> Path:
        return (
            self._root
            / safe_scope_component(scope.agent_id)
            / safe_scope_component(scope.user_id)
        )

def create_long_term_memory(settings: Settings) -> LongTermMemory:
    """Create the configured long-term memory backend."""
    if settings.memory_backend == "disabled":
        return DisabledLongTermMemory()
    if settings.memory_backend == "local_markdown":
        return LocalMarkdownMemory(settings.sighttalk_data_dir)
    if settings.memory_backend == "local_jsonl":
        return LocalJsonlLongTermMemory(MemoryStore(settings.sighttalk_data_dir))
    raise ValueError(f"Unsupported MEMORY_BACKEND: {settings.memory_backend}")


def safe_scope_component(value: str) -> str:
    """Return a filesystem-safe scope component."""
    stripped = value.strip() or "default"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", stripped)[:120]


def compact_memory_text(text: str) -> str:
    """Collapse transcript whitespace before writing markdown memory files."""
    return " ".join(text.split()).strip()


def keyword_terms(query: str) -> list[str]:
    """Extract grep-like case-insensitive search terms."""
    return [
        term
        for term in re.split(r"\W+", query.lower())
        if len(term) >= 2
    ]


def read_markdown_payload(path: Path) -> str:
    """Read markdown content, ignoring empty files and title-only defaults."""
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8").strip()
    lines = [
        line.rstrip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return "\n".join(lines).strip()


def read_memory_fact_lines(path: Path) -> list[str]:
    """Read existing MEMORY.md fact lines without headings."""
    payload = read_markdown_payload(path)
    return [line.strip() for line in payload.splitlines() if line.strip()]


def matching_history_entries(path: Path, query_terms: Sequence[str], *, limit: int) -> list[str]:
    """Return newest HISTORY.md entries matching at least one query term."""
    entries = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("- [")
    ]
    matches = [
        entry
        for entry in reversed(entries)
        if any(term in entry.lower() for term in query_terms)
    ]
    return list(reversed(matches[: max(limit, 1)]))


def should_promote_to_memory(text: str) -> bool:
    """Return whether user text looks like a durable fact or preference."""
    lowered = text.lower()
    return any(trigger in lowered for trigger in LOCAL_MARKDOWN_FACT_TRIGGERS)


def normalize_fact_line(line: str) -> str:
    """Normalize a memory fact line for exact de-duplication."""
    return re.sub(r"\s+", " ", line.strip().lower())
