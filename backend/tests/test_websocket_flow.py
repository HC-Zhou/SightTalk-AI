from fastapi.testclient import TestClient

from sighttalk_api.main import app


def test_websocket_mock_turn_flow_returns_expected_events() -> None:
    client = TestClient(app)

    with client.websocket_connect("/ws/session/test-session") as websocket:
        websocket.send_json({"type": "session.start"})
        ready = websocket.receive_json()
        assert ready["type"] == "session.ready"
        assert ready["policy"]["max_keyframes_per_turn"] == 3

        websocket.send_json(
            {
                "type": "video.frame",
                "seq": 1,
                "mime": "image/jpeg",
                "captured_at": 1000,
                "data": "image-a",
            }
        )
        websocket.send_json(
            {
                "type": "audio.chunk",
                "seq": 1,
                "mime": "audio/webm",
                "data": "audio-a",
            }
        )
        websocket.send_json({"type": "utterance.end", "audio_seq_end": 1})

        events = [websocket.receive_json() for _ in range(6)]
        assert [event["type"] for event in events] == [
            "transcript.final",
            "assistant.thinking",
            "assistant.text.delta",
            "assistant.text.done",
            "tts.ready",
            "cost.snapshot",
        ]
        assert events[-1]["asr_calls"] == 1
        assert events[-1]["vision_llm_calls"] == 1
        assert events[-1]["tts_calls"] == 1


def test_audio_endpoint_serves_mock_tts_audio_after_turn() -> None:
    client = TestClient(app)

    with client.websocket_connect("/ws/session/audio-session") as websocket:
        websocket.send_json({"type": "session.start"})
        websocket.receive_json()
        websocket.send_json(
            {
                "type": "video.frame",
                "seq": 1,
                "mime": "image/jpeg",
                "captured_at": 1000,
                "data": "image-a",
            }
        )
        websocket.send_json(
            {
                "type": "audio.chunk",
                "seq": 1,
                "mime": "audio/webm",
                "data": "audio-a",
            }
        )
        websocket.send_json({"type": "utterance.end", "audio_seq_end": 1})
        events = [websocket.receive_json() for _ in range(5)]
        audio_url = events[-1]["audio_url"]

    response = client.get(audio_url)
    assert response.status_code == 200
    assert response.content == b"mock-audio"
