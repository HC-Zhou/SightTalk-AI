from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sighttalk_api.agent.context import BASE_SYSTEM_PROMPT, AgentSessionContext
from sighttalk_api.schemas.livekit import MediaPolicy
from sighttalk_api.services.long_term_memory import (
    MemoryMessage,
    MemoryScope,
    NanobotMarkdownMemory,
)
from sighttalk_api.services.memory import MemoryRecord, MemoryStore


def make_policy() -> MediaPolicy:
    return MediaPolicy(
        mode="balanced",
        max_video_fps=1.0,
        max_jpeg_edge=1024,
        jpeg_quality=75,
        vad_enabled=True,
    )


def make_scope(user_id: str = "user_1", run_id: str = "room-1") -> MemoryScope:
    return MemoryScope(user_id=user_id, agent_id="sighttalk", run_id=run_id)


def test_memory_store_isolates_users_and_limits_recent_items(tmp_path) -> None:
    store = MemoryStore(tmp_path)
    now = datetime.now(tz=UTC)
    for index in range(5):
        store.append(
            MemoryRecord(
                user_id="user_1",
                session_id=f"session-{index}",
                timestamp=now + timedelta(seconds=index),
                speaker="user",
                text=f"memory {index}",
            )
        )
    store.append(
        MemoryRecord(
            user_id="user_2",
            session_id="session-other",
            timestamp=now,
            speaker="assistant",
            text="other user memory",
        )
    )

    records = store.recent(user_id="user_1", limit=3)

    assert [record.text for record in records] == ["memory 2", "memory 3", "memory 4"]
    assert all(record.user_id == "user_1" for record in records)


def test_memory_store_ignores_malformed_lines(tmp_path) -> None:
    store = MemoryStore(tmp_path)
    store.append(
        MemoryRecord(
            user_id="user_1",
            session_id="session-1",
            timestamp=datetime.now(tz=UTC),
            speaker="user",
            text="valid memory",
        )
    )
    path = tmp_path / "memory" / "user_1.jsonl"
    with path.open("a", encoding="utf-8") as file:
        file.write("{bad-json\n")

    records = store.recent(user_id="user_1", limit=10)

    assert [record.text for record in records] == ["valid memory"]


def test_context_prompt_injects_memory_only_when_present(tmp_path) -> None:
    store = MemoryStore(tmp_path)
    empty_context = AgentSessionContext(
        session_id="room-1",
        user_id="user_1",
        media_policy=make_policy(),
        memory_store=store,
        memory_max_items=3,
    )

    assert empty_context.build_system_prompt() == BASE_SYSTEM_PROMPT

    store.append(
        MemoryRecord(
            user_id="user_1",
            session_id="old-room",
            timestamp=datetime.now(tz=UTC),
            speaker="user",
            text="My desk lamp is blue.",
        )
    )

    prompt = empty_context.build_system_prompt()

    assert BASE_SYSTEM_PROMPT in prompt
    assert "User memory from previous SightTalk sessions" in prompt
    assert "My desk lamp is blue." in prompt


async def test_context_async_prompt_injects_nanobot_memory_without_query(tmp_path) -> None:
    memory = NanobotMarkdownMemory(tmp_path)
    await memory.add_turn(
        make_scope("user_1"),
        [MemoryMessage(role="user", content="请记住，我喜欢蓝色台灯。")],
        {"session_id": "old-room", "turn_id": "turn-1"},
    )
    context = AgentSessionContext(
        session_id="room-1",
        user_id="user_1",
        media_policy=make_policy(),
        long_term_memory=memory,
    )

    prompt = await context.build_system_prompt_async()

    assert "User memory from previous SightTalk sessions" in prompt
    assert "请记住，我喜欢蓝色台灯。" in prompt


async def test_context_consolidates_short_term_memory_to_nanobot_history(tmp_path) -> None:
    memory = NanobotMarkdownMemory(tmp_path)
    context = AgentSessionContext(
        session_id="room-1",
        user_id="user_1",
        media_policy=make_policy(),
        short_memory_max_messages=1,
        long_term_memory=memory,
    )
    for index in range(6):
        context.record_transcript(
            speaker="user",
            text=f"message {index}",
            message_id=f"message-{index}",
            final=True,
        )

    assert await context.flush_memory_async() == 6

    history = (
        tmp_path / "nanobot" / "sighttalk" / "user_1" / "HISTORY.md"
    ).read_text(encoding="utf-8")
    assert "sighttalk_short_context_consolidation" in history
    assert "summary: user: message 0 user: message 1" in history
    assert [turn.text for turn in context.context_worker.context.finalized_turns] == [
        "message 2",
        "message 3",
        "message 4",
        "message 5",
    ]


def test_context_flushes_final_transcripts_once(tmp_path) -> None:
    store = MemoryStore(tmp_path)
    context = AgentSessionContext(
        session_id="room-1",
        user_id="user_1",
        media_policy=make_policy(),
        memory_store=store,
        memory_max_items=10,
    )
    context.record_transcript(
        speaker="user",
        text="hello",
        message_id="message-1",
        final=True,
    )

    assert context.flush_memory() == 1
    assert context.flush_memory() == 0
    assert [record.text for record in store.recent(user_id="user_1", limit=10)] == ["hello"]


def test_context_does_not_flush_empty_or_unfinalized_text(tmp_path) -> None:
    store = MemoryStore(tmp_path)
    context = AgentSessionContext(
        session_id="room-1",
        user_id="user_1",
        media_policy=make_policy(),
        memory_store=store,
        memory_max_items=10,
    )
    context.record_transcript(
        speaker="assistant",
        text="",
        message_id="empty",
        final=True,
    )
    context.record_transcript(
        speaker="assistant",
        text="partial",
        message_id="partial",
        final=False,
    )

    assert context.flush_memory() == 0
    assert store.recent(user_id="user_1", limit=10) == []
