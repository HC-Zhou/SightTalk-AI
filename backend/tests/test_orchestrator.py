import pytest

from sighttalk_api.ai.mock_adapters import MockAsrAdapter, MockMultimodalAdapter, MockTtsAdapter
from sighttalk_api.ai.orchestrator import DialogueOrchestrator
from sighttalk_api.core.session import SessionStore
from sighttalk_api.media.audio_buffer import AudioChunk
from sighttalk_api.media.frame_buffer import FrameItem
from sighttalk_api.storage.audio_store import InMemoryAudioStore


@pytest.mark.asyncio
async def test_orchestrator_turn_returns_transcript_answer_tts_and_cost() -> None:
    store = SessionStore()
    session = store.get_or_create("s1")
    session.audio_buffer.add(AudioChunk(seq=1, mime="audio/webm", data="hello"))
    session.frame_buffer.add(FrameItem(seq=1, captured_at=1000, mime="image/jpeg", data="frame-1"))
    session.frame_buffer.add(FrameItem(seq=2, captured_at=1002, mime="image/jpeg", data="frame-2"))

    audio_store = InMemoryAudioStore()
    orchestrator = DialogueOrchestrator(
        asr=MockAsrAdapter(text="What am I holding?"),
        multimodal=MockMultimodalAdapter(answer="It looks like you are holding a mug."),
        tts=MockTtsAdapter(audio_bytes=b"voice"),
        audio_store=audio_store,
    )

    events = await orchestrator.handle_utterance_end(session=session, audio_seq_end=1)

    assert [event.type for event in events] == [
        "transcript.final",
        "assistant.thinking",
        "assistant.text.delta",
        "assistant.text.done",
        "tts.ready",
        "cost.snapshot",
    ]
    assert events[0].text == "What am I holding?"
    assert events[3].text == "It looks like you are holding a mug."
    assert events[4].audio_url == "/api/v1/audio/s1-turn-2.wav"
    assert events[5].frames_sent_to_model == 2
    assert audio_store.get("s1-turn-2.wav") == b"voice"
    assert session.conversation_history[0].role == "user"
    assert session.conversation_history[1].role == "assistant"
