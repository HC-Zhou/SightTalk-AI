from sighttalk_api.core.session import SessionStore
from sighttalk_api.media.audio_buffer import AudioChunk
from sighttalk_api.media.frame_buffer import FrameItem


def test_session_store_creates_and_returns_same_session() -> None:
    store = SessionStore()

    first = store.get_or_create("abc")
    second = store.get_or_create("abc")

    assert first is second
    assert first.session_id == "abc"


def test_session_tracks_audio_frames_and_history() -> None:
    store = SessionStore()
    session = store.get_or_create("abc")

    session.audio_buffer.add(AudioChunk(seq=1, mime="audio/webm", data="audio"))
    session.frame_buffer.add(FrameItem(seq=1, captured_at=1000, mime="image/jpeg", data="image"))
    session.add_turn(role="user", text="What is this?", frame_refs=["frame-1"])

    assert session.audio_buffer.chunks[0].data == "audio"
    assert session.frame_buffer.frames[0].data == "image"
    assert session.conversation_history[0].text == "What is this?"


def test_session_history_is_trimmed_to_limit() -> None:
    store = SessionStore(history_limit=2)
    session = store.get_or_create("abc")

    session.add_turn(role="user", text="one", frame_refs=[])
    session.add_turn(role="assistant", text="two", frame_refs=[])
    session.add_turn(role="user", text="three", frame_refs=[])

    assert [turn.text for turn in session.conversation_history] == ["two", "three"]
