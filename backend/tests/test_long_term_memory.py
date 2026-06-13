from __future__ import annotations

from sighttalk_api.core.config import Settings
from sighttalk_api.services.long_term_memory import (
    DisabledLongTermMemory,
    LocalJsonlLongTermMemory,
    LocalMarkdownMemory,
    MemoryMessage,
    MemoryScope,
    create_long_term_memory,
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


async def test_local_markdown_memory_writes_readable_memory_and_history(tmp_path) -> None:
    memory = LocalMarkdownMemory(tmp_path)
    scope = make_scope("user/1")

    await memory.add_turn(
        scope,
        [
            MemoryMessage(role="user", content="请记住，我喜欢冷白色灯光。"),
            MemoryMessage(role="assistant", content="好的，我会记住。"),
        ],
        {"session_id": "room-1", "turn_id": "turn-1", "source": "sighttalk_realtime"},
    )

    memory_path = tmp_path / "markdown_memory" / "sighttalk" / "user_1" / "MEMORY.md"
    history_path = tmp_path / "markdown_memory" / "sighttalk" / "user_1" / "HISTORY.md"

    assert "请记住，我喜欢冷白色灯光。" in memory_path.read_text(encoding="utf-8")
    assert "assistant: 好的，我会记住。" in history_path.read_text(encoding="utf-8")
    assert [result.text for result in await memory.search(scope, "", limit=5, threshold=0.3)] == [
        "MEMORY.md:\n- 请记住，我喜欢冷白色灯光。"
    ]


async def test_local_markdown_memory_searches_history_without_cross_user_leak(
    tmp_path,
) -> None:
    memory = LocalMarkdownMemory(tmp_path)
    user_scope = make_scope("user-1")
    other_scope = make_scope("user-2")

    await memory.add_turn(
        user_scope,
        [MemoryMessage(role="user", content="我的台灯是蓝色的。")],
        {"session_id": "room-1", "turn_id": "turn-1"},
    )
    await memory.add_turn(
        other_scope,
        [MemoryMessage(role="user", content="我的台灯是红色的。")],
        {"session_id": "room-2", "turn_id": "turn-1"},
    )

    results = await memory.search(user_scope, "蓝色 台灯", limit=5, threshold=0.3)

    assert any("蓝色" in result.text for result in results)
    assert all("红色" not in result.text for result in results)


async def test_local_markdown_memory_appends_short_term_summary(tmp_path) -> None:
    memory = LocalMarkdownMemory(tmp_path)
    scope = make_scope("user-1")

    await memory.add_short_term_summary(
        scope,
        "user: asked about lamp setup\nassistant: compared lighting options",
        {"session_id": "room-1", "turn_ids": ["turn-1", "turn-2"]},
    )

    history = (
        tmp_path / "markdown_memory" / "sighttalk" / "user-1" / "HISTORY.md"
    ).read_text(encoding="utf-8")
    assert "summary: user: asked about lamp setup assistant: compared lighting options" in history


async def test_create_long_term_memory_selects_local_and_disabled_backends(tmp_path) -> None:
    markdown = create_long_term_memory(
        Settings(sighttalk_data_dir=tmp_path, memory_backend="local_markdown")
    )
    local = create_long_term_memory(
        Settings(sighttalk_data_dir=tmp_path, memory_backend="local_jsonl")
    )
    disabled = create_long_term_memory(
        Settings(sighttalk_data_dir=tmp_path, memory_backend="disabled")
    )

    assert isinstance(markdown, LocalMarkdownMemory)
    assert isinstance(local, LocalJsonlLongTermMemory)
    assert isinstance(disabled, DisabledLongTermMemory)
