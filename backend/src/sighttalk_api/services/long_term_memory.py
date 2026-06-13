"""Long-term memory protocol and backend adapters."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import logging
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, cast

from sighttalk_api.core.config import Settings
from sighttalk_api.services.memory import MemoryStore, memory_record_now

MemoryRole = Literal["user", "assistant"]


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


class Mem0ClientProtocol(Protocol):
    """Minimal client surface used by `Mem0LongTermMemory`."""

    def search(self, **kwargs: Any) -> Any:
        raise NotImplementedError

    def add(self, **kwargs: Any) -> Any:
        raise NotImplementedError


class Mem0LongTermMemory:
    """Mem0-compatible long-term memory adapter.

    The adapter accepts an injected client so tests and CI do not require the external
    Mem0 package or network service.
    """

    def __init__(self, client: Mem0ClientProtocol) -> None:
        self._client = client

    async def search(
        self,
        scope: MemoryScope,
        query: str,
        *,
        limit: int,
        threshold: float,
    ) -> list[MemorySearchResult]:
        """Search Mem0 using user and agent filters, intentionally excluding run id."""
        if not query.strip():
            return []
        try:
            payload = await _call_client_method(
                self._client.search,
                query=query,
                filters=mem0_scope_filters(scope),
                top_k=limit,
                threshold=threshold,
            )
        except ValueError as exc:
            if "filters must contain at least one" not in str(exc):
                raise
            payload = await _call_client_method(
                self._client.search,
                query=query,
                filters=mem0_flat_scope_filters(scope),
                top_k=limit,
                threshold=threshold,
            )
        return normalize_mem0_results(payload)

    async def add_turn(
        self,
        scope: MemoryScope,
        messages: Sequence[MemoryMessage],
        metadata: Mapping[str, Any],
    ) -> None:
        """Store a completed turn in Mem0 with inference enabled."""
        payload = [
            {"role": message.role, "content": message.content.strip()}
            for message in messages
            if message.content.strip()
        ]
        if not payload:
            return
        await _call_client_method(
            self._client.add,
            messages=payload,
            user_id=scope.user_id,
            agent_id=scope.agent_id,
            run_id=scope.run_id,
            metadata=dict(metadata),
            infer=True,
        )

    async def close(self) -> None:
        """Close the injected client if it exposes a close method."""
        close = getattr(self._client, "close", None)
        if close is None:
            return
        await _call_client_method(close)


class LazyLongTermMemory:
    """Instantiate a long-term memory backend only when it is first used."""

    def __init__(self, factory: Callable[[], LongTermMemory]) -> None:
        self._factory = factory
        self._memory: LongTermMemory | None = None
        self._lock = asyncio.Lock()

    async def search(
        self,
        scope: MemoryScope,
        query: str,
        *,
        limit: int,
        threshold: float,
    ) -> list[MemorySearchResult]:
        """Search the lazily-created backend."""
        if not query.strip():
            return []
        memory = await self._ensure_memory()
        return await memory.search(scope, query, limit=limit, threshold=threshold)

    async def add_turn(
        self,
        scope: MemoryScope,
        messages: Sequence[MemoryMessage],
        metadata: Mapping[str, Any],
    ) -> None:
        """Persist through the lazily-created backend."""
        if not any(message.content.strip() for message in messages):
            return
        memory = await self._ensure_memory()
        await memory.add_turn(scope, messages, metadata)

    async def close(self) -> None:
        """Close the backend if it has been created."""
        if self._memory is not None:
            await self._memory.close()

    async def _ensure_memory(self) -> LongTermMemory:
        if self._memory is not None:
            return self._memory
        async with self._lock:
            if self._memory is None:
                self._memory = await asyncio.to_thread(self._factory)
        return self._memory


def mem0_scope_filters(scope: MemoryScope) -> dict[str, list[dict[str, str]]]:
    """Return the Mem0 entity filter shape for cross-session user recall."""
    return {"AND": [{"user_id": scope.user_id}, {"agent_id": scope.agent_id}]}


def mem0_flat_scope_filters(scope: MemoryScope) -> dict[str, str]:
    """Return the Mem0 OSS SDK entity filter shape."""
    return {"user_id": scope.user_id, "agent_id": scope.agent_id}


def normalize_mem0_results(payload: Any) -> list[MemorySearchResult]:
    """Normalize common Mem0 search response shapes."""
    raw_results = payload.get("results", []) if isinstance(payload, Mapping) else payload
    if not isinstance(raw_results, Sequence) or isinstance(raw_results, (str, bytes)):
        return []

    results: list[MemorySearchResult] = []
    for item in raw_results:
        if isinstance(item, str):
            text = item
            score = None
            metadata: Mapping[str, Any] = {}
        elif isinstance(item, Mapping):
            text = str(item.get("memory") or item.get("text") or item.get("content") or "")
            raw_score = item.get("score")
            score = float(raw_score) if isinstance(raw_score, int | float) else None
            raw_metadata = item.get("metadata", {})
            metadata = raw_metadata if isinstance(raw_metadata, Mapping) else {}
        else:
            continue
        if text.strip():
            results.append(MemorySearchResult(text=text.strip(), score=score, metadata=metadata))
    return results


def create_long_term_memory(
    settings: Settings,
    *,
    mem0_client: Mem0ClientProtocol | None = None,
) -> LongTermMemory:
    """Create the configured long-term memory backend."""
    if settings.memory_backend == "disabled":
        return DisabledLongTermMemory()
    if settings.memory_backend == "local_jsonl":
        return LocalJsonlLongTermMemory(MemoryStore(settings.sighttalk_data_dir))
    if mem0_client is None:
        return LazyLongTermMemory(
            lambda: Mem0LongTermMemory(create_mem0_sdk_client(settings))
        )
    return Mem0LongTermMemory(mem0_client)


def create_mem0_sdk_client(settings: Settings) -> Mem0ClientProtocol:
    """Create a real Mem0 SDK client from settings."""
    configure_mem0_optional_dependency_logging()
    mem0_module = importlib.import_module("mem0")

    if settings.mem0_local_config_json.strip():
        config = json.loads(os.path.expandvars(settings.mem0_local_config_json))
        if not isinstance(config, dict):
            raise ValueError("MEM0_LOCAL_CONFIG_JSON must decode to a JSON object")
        memory_class = cast(Any, mem0_module).Memory
        return cast(Mem0ClientProtocol, memory_class.from_config(config))
    if not (settings.mem0_api_key or settings.mem0_host):
        raise ValueError(
            "MEMORY_BACKEND=mem0 requires MEM0_API_KEY, MEM0_HOST, "
            "or MEM0_LOCAL_CONFIG_JSON"
        )
    memory_client_class = cast(Any, mem0_module).MemoryClient
    return cast(Mem0ClientProtocol, memory_client_class(
        api_key=settings.mem0_api_key or None,
        host=settings.mem0_host or None,
    ))


def configure_mem0_optional_dependency_logging() -> None:
    """Hide Mem0's optional spaCy fallback warnings in local OSS mode."""
    logging.getLogger("mem0.utils.spacy_models").setLevel(logging.ERROR)


async def _maybe_await(value: Any) -> Any:
    """Await coroutine-like values and return plain values unchanged."""
    if inspect.isawaitable(value):
        return await value
    return value


async def _call_client_method(method: Callable[..., Any], **kwargs: Any) -> Any:
    """Call sync SDK methods off the event loop and await async methods directly."""
    if inspect.iscoroutinefunction(method):
        return await method(**kwargs)
    return await asyncio.to_thread(method, **kwargs)
