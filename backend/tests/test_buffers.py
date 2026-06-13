from sighttalk_api.media.audio_buffer import AudioBuffer, AudioChunk
from sighttalk_api.media.frame_buffer import FrameBuffer, FrameItem
from sighttalk_api.media.keyframe_selector import select_keyframes


def test_audio_buffer_collects_chunks_until_sequence() -> None:
    buffer = AudioBuffer(max_chunks=3)
    buffer.add(AudioChunk(seq=1, mime="audio/webm", data="a"))
    buffer.add(AudioChunk(seq=2, mime="audio/webm", data="b"))
    buffer.add(AudioChunk(seq=3, mime="audio/webm", data="c"))

    chunks = buffer.collect_until(seq_end=2)

    assert [chunk.seq for chunk in chunks] == [1, 2]
    assert [chunk.seq for chunk in buffer.chunks] == [3]


def test_audio_buffer_discards_oldest_when_full() -> None:
    buffer = AudioBuffer(max_chunks=2)
    buffer.add(AudioChunk(seq=1, mime="audio/webm", data="a"))
    buffer.add(AudioChunk(seq=2, mime="audio/webm", data="b"))
    buffer.add(AudioChunk(seq=3, mime="audio/webm", data="c"))

    assert [chunk.seq for chunk in buffer.chunks] == [2, 3]


def test_frame_buffer_keeps_recent_frames() -> None:
    buffer = FrameBuffer(max_frames=3)
    for seq in range(5):
        buffer.add(FrameItem(seq=seq, captured_at=1000 + seq, mime="image/jpeg", data=f"img-{seq}"))

    assert [frame.seq for frame in buffer.frames] == [2, 3, 4]


def test_select_keyframes_prefers_recent_frames() -> None:
    frames = [
        FrameItem(seq=1, captured_at=1001, mime="image/jpeg", data="a"),
        FrameItem(seq=2, captured_at=1002, mime="image/jpeg", data="b"),
        FrameItem(seq=3, captured_at=1003, mime="image/jpeg", data="c"),
        FrameItem(seq=4, captured_at=1004, mime="image/jpeg", data="d"),
    ]

    selected = select_keyframes(frames, limit=3)

    assert [frame.seq for frame in selected] == [2, 3, 4]

