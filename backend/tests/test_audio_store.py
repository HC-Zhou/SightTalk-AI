from sighttalk_api.storage.audio_store import InMemoryAudioStore


def test_audio_store_saves_and_returns_url() -> None:
    store = InMemoryAudioStore()

    url = store.save(session_id="s1", turn_id=2, audio_bytes=b"voice")

    assert url == "/api/v1/audio/s1-turn-2.wav"
    assert store.get("s1-turn-2.wav") == b"voice"

