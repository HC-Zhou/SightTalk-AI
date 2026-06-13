from __future__ import annotations

from sighttalk_api.services.livekit_messenger import livekit_http_url


def test_livekit_http_url_converts_websocket_urls() -> None:
    assert livekit_http_url("ws://localhost:7880") == "http://localhost:7880"
    assert livekit_http_url("wss://livekit.example") == "https://livekit.example"
    assert livekit_http_url("http://localhost:7880") == "http://localhost:7880"
