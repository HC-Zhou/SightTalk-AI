from __future__ import annotations

from livekit import api

from sighttalk_api.core.errors import AppError
from sighttalk_api.services.livekit_messenger import livekit_http_url


class LiveKitRoomService:
    def __init__(self, *, url: str, api_key: str, api_secret: str) -> None:
        self._url = livekit_http_url(url)
        self._api_key = api_key
        self._api_secret = api_secret

    async def ensure_room(self, *, room_name: str) -> None:
        client = api.LiveKitAPI(
            url=self._url,
            api_key=self._api_key,
            api_secret=self._api_secret,
        )
        try:
            await client.room.create_room(
                api.CreateRoomRequest(
                    name=room_name,
                    empty_timeout=300,
                    departure_timeout=20,
                )
            )
        except Exception as exc:
            if "already exists" in str(exc).lower():
                return
            raise AppError(
                "LIVEKIT_ROOM_CREATE_FAILED",
                f"Unable to create LiveKit room: {exc}",
                status_code=502,
            ) from exc
        finally:
            await client.aclose()  # type: ignore[no-untyped-call]
