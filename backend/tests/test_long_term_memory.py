from __future__ import annotations

import logging
from typing import Any

from sighttalk_api.core.config import Settings
from sighttalk_api.services.long_term_memory import (
    DisabledLongTermMemory,
    LazyLongTermMemory,
    LocalJsonlLongTermMemory,
    Mem0LongTermMemory,
    MemoryMessage,
    MemoryScope,
    configure_mem0_optional_dependency_logging,
    create_long_term_memory,
    create_mem0_sdk_client,
    mem0_flat_scope_filters,
    mem0_scope_filters,
)
from sighttalk_api.services.memory import MemoryStore


def make_scope(user_id: str = "user-1", run_id: str = "room-1") -> MemoryScope:
    return MemoryScope(user_id=user_id, agent_id="sighttalk", run_id=run_id)


async def test_disabled_long_term_memory_is_non_fatal() -> None:
    memory = DisabledLongTermMemory()

    assert await memory.search(make_scope(), "anything", limit=5, threshold=0.3) == []
    await memory.add_turn(make_scope(), [MemoryMessage(role="user", content="hello")], {})
    await memory.close()


async def test_local_jsonl_long_term_memory_isolates_users_and_skips_empty_text(
    tmp_path,
) -> None:
    store = MemoryStore(tmp_path)
    memory = LocalJsonlLongTermMemory(store)
    metadata = {"session_id": "room-1"}

    await memory.add_turn(
        make_scope("user-1"),
        [
            MemoryMessage(role="user", content="My desk lamp is blue."),
            MemoryMessage(role="assistant", content="  "),
        ],
        metadata,
    )
    await memory.add_turn(
        make_scope("user-2"),
        [MemoryMessage(role="user", content="Other user memory.")],
        {"session_id": "room-2"},
    )

    results = await memory.search(make_scope("user-1"), "lamp", limit=5, threshold=0.3)

    assert [result.text for result in results] == ["user: My desk lamp is blue."]
    assert store.recent(user_id="user-2", limit=5)[0].text == "Other user memory."


async def test_mem0_long_term_memory_uses_scope_filters_and_threshold() -> None:
    client = FakeMem0Client()
    memory = Mem0LongTermMemory(client)
    scope = make_scope()

    results = await memory.search(scope, "desk", limit=3, threshold=0.42)

    assert client.search_calls == [
        {
            "query": "desk",
            "filters": {"AND": [{"user_id": "user-1"}, {"agent_id": "sighttalk"}]},
            "top_k": 3,
            "threshold": 0.42,
        }
    ]
    assert results[0].text == "User likes blue lamps."
    assert results[0].score == 0.9
    assert mem0_scope_filters(scope) == {
        "AND": [{"user_id": "user-1"}, {"agent_id": "sighttalk"}]
    }


async def test_mem0_long_term_memory_skips_empty_search_query() -> None:
    client = FakeMem0Client()
    memory = Mem0LongTermMemory(client)

    results = await memory.search(make_scope(), "   ", limit=3, threshold=0.42)

    assert results == []
    assert client.search_calls == []


async def test_mem0_long_term_memory_falls_back_to_oss_flat_filters() -> None:
    client = FakeOssMem0Client()
    memory = Mem0LongTermMemory(client)
    scope = make_scope()

    results = await memory.search(scope, "desk", limit=3, threshold=0.42)

    assert client.search_calls == [
        {
            "query": "desk",
            "filters": {"AND": [{"user_id": "user-1"}, {"agent_id": "sighttalk"}]},
            "top_k": 3,
            "threshold": 0.42,
        },
        {
            "query": "desk",
            "filters": {"user_id": "user-1", "agent_id": "sighttalk"},
            "top_k": 3,
            "threshold": 0.42,
        },
    ]
    assert results[0].text == "Flat filter memory."
    assert mem0_flat_scope_filters(scope) == {
        "user_id": "user-1",
        "agent_id": "sighttalk",
    }


async def test_mem0_long_term_memory_adds_turn_with_metadata_and_infer() -> None:
    client = FakeMem0Client()
    memory = Mem0LongTermMemory(client)
    metadata = {
        "session_id": "room-1",
        "turn_id": "turn-1",
        "media_mode": "balanced",
        "has_visual_context": True,
        "source": "sighttalk_realtime",
    }

    await memory.add_turn(
        make_scope(),
        [
            MemoryMessage(role="user", content="I prefer cool light."),
            MemoryMessage(role="assistant", content=""),
        ],
        metadata,
    )

    assert client.add_calls == [
        {
            "messages": [{"role": "user", "content": "I prefer cool light."}],
            "user_id": "user-1",
            "agent_id": "sighttalk",
            "run_id": "room-1",
            "metadata": metadata,
            "infer": True,
        }
    ]


async def test_create_long_term_memory_selects_local_and_disabled_backends(tmp_path) -> None:
    local = create_long_term_memory(
        Settings(sighttalk_data_dir=tmp_path, memory_backend="local_jsonl")
    )
    disabled = create_long_term_memory(
        Settings(sighttalk_data_dir=tmp_path, memory_backend="disabled")
    )

    assert isinstance(local, LocalJsonlLongTermMemory)
    assert isinstance(disabled, DisabledLongTermMemory)


async def test_create_long_term_memory_selects_real_mem0_backend_with_injected_client(
    tmp_path,
) -> None:
    client = FakeMem0Client()

    memory = create_long_term_memory(
        Settings(
            sighttalk_data_dir=tmp_path,
            memory_backend="mem0",
            mem0_api_key="key",
        ),
        mem0_client=client,
    )

    assert isinstance(memory, Mem0LongTermMemory)


async def test_create_long_term_memory_lazily_initializes_real_mem0_backend(tmp_path) -> None:
    memory = create_long_term_memory(
        Settings(
            sighttalk_data_dir=tmp_path,
            memory_backend="mem0",
            mem0_api_key="key",
        )
    )

    assert isinstance(memory, LazyLongTermMemory)


def test_create_mem0_sdk_client_requires_configuration_for_mem0(tmp_path) -> None:
    settings = Settings(sighttalk_data_dir=tmp_path, memory_backend="mem0")

    try:
        create_mem0_sdk_client(settings)
    except ValueError as exc:
        assert "MEMORY_BACKEND=mem0 requires" in str(exc)
    else:
        raise AssertionError("Expected missing Mem0 configuration to fail")


def test_configure_mem0_optional_dependency_logging_hides_spacy_warning() -> None:
    logger = logging.getLogger("mem0.utils.spacy_models")
    original_level = logger.level
    try:
        logger.setLevel(logging.NOTSET)
        configure_mem0_optional_dependency_logging()

        assert logger.level == logging.ERROR
    finally:
        logger.setLevel(original_level)


class FakeMem0Client:
    def __init__(self) -> None:
        self.search_calls: list[dict[str, Any]] = []
        self.add_calls: list[dict[str, Any]] = []

    def search(self, **kwargs: Any) -> dict[str, list[dict[str, Any]]]:
        self.search_calls.append(dict(kwargs))
        return {
            "results": [
                {
                    "memory": "User likes blue lamps.",
                    "score": 0.9,
                    "metadata": {"session_id": "old-room"},
                }
            ]
        }

    def add(self, **kwargs: Any) -> None:
        self.add_calls.append(dict(kwargs))


class FakeOssMem0Client(FakeMem0Client):
    def search(self, **kwargs: Any) -> dict[str, list[dict[str, Any]]]:
        self.search_calls.append(dict(kwargs))
        filters = kwargs.get("filters")
        if isinstance(filters, dict) and "AND" in filters:
            raise ValueError("filters must contain at least one of: user_id, agent_id, run_id")
        return {
            "results": [
                {
                    "memory": "Flat filter memory.",
                    "score": 0.8,
                }
            ]
        }
