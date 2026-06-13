from __future__ import annotations

from sighttalk_api.agent.livekit_runtime import LiveKitRoomAgent
from sighttalk_api.core.config import Settings
from sighttalk_api.schemas.livekit import MediaPolicy
from sighttalk_api.services.long_term_memory import Mem0LongTermMemory


async def test_livekit_room_agent_assembles_worker_runner(tmp_path) -> None:
    agent = LiveKitRoomAgent(
        room_name="room-1",
        livekit_url="ws://localhost:7880",
        assistant_token="token",
        settings=Settings(
            ai_provider="mock",
            sighttalk_data_dir=tmp_path,
        ),
        media_policy=MediaPolicy(
            mode="balanced",
            max_video_fps=1.0,
            max_jpeg_edge=1024,
            jpeg_quality=75,
            vad_enabled=True,
        ),
        user_id="user-1",
    )

    registry = agent._registry  # noqa: SLF001

    assert registry.get("transport") is not None
    assert registry.get("provider") is not None
    assert registry.get("context") is not None
    assert registry.get("memory") is not None
    assert registry.get("main") is not None


async def test_livekit_room_agent_uses_configured_mem0_backend(
    tmp_path,
    monkeypatch,
) -> None:
    fake_client = FakeMem0Client()

    def fake_create_long_term_memory(settings: Settings) -> Mem0LongTermMemory:
        return Mem0LongTermMemory(fake_client)

    monkeypatch.setattr(
        "sighttalk_api.agent.livekit_runtime.create_long_term_memory",
        fake_create_long_term_memory,
    )

    agent = LiveKitRoomAgent(
        room_name="room-1",
        livekit_url="ws://localhost:7880",
        assistant_token="token",
        settings=Settings(
            ai_provider="mock",
            memory_backend="mem0",
            mem0_api_key="key",
            sighttalk_data_dir=tmp_path,
        ),
        media_policy=MediaPolicy(
            mode="balanced",
            max_video_fps=1.0,
            max_jpeg_edge=1024,
            jpeg_quality=75,
            vad_enabled=True,
        ),
        user_id="user-1",
    )

    memory_worker = agent._context.memory_worker  # noqa: SLF001

    assert isinstance(memory_worker.memory, Mem0LongTermMemory)


class FakeMem0Client:
    def search(self, **kwargs: object) -> dict[str, list[dict[str, object]]]:
        return {"results": []}

    def add(self, **kwargs: object) -> None:
        return
