"""LiveKit server-side data-message publishing helpers."""

from __future__ import annotations

import json

from livekit import api


def livekit_http_url(livekit_url: str) -> str:
    """Convert a browser-facing LiveKit WebSocket URL to the HTTP API URL."""
    if livekit_url.startswith("ws://"):
        return f"http://{livekit_url.removeprefix('ws://')}"
    if livekit_url.startswith("wss://"):
        return f"https://{livekit_url.removeprefix('wss://')}"
    return livekit_url


class LiveKitMessenger:
    """Publishes reliable JSON data packets to participants in a LiveKit room."""

    def __init__(self, *, url: str, api_key: str, api_secret: str) -> None:
        self._url = livekit_http_url(url)
        self._api_key = api_key
        self._api_secret = api_secret

    async def send_json(self, *, room_name: str, topic: str, payload: dict[str, object]) -> None:
        """Send a UTF-8 JSON payload over the requested LiveKit data topic."""
        client = api.LiveKitAPI(
            url=self._url,
            api_key=self._api_key,
            api_secret=self._api_secret,
        )
        try:
            await client.room.send_data(
                api.SendDataRequest(
                    room=room_name,
                    topic=topic,
                    kind=api.DataPacket.Kind.RELIABLE,
                    data=json.dumps(payload).encode("utf-8"),
                )
            )
        finally:
            await client.aclose()  # type: ignore[no-untyped-call]
