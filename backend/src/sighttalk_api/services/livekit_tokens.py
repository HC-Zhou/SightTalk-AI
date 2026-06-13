from __future__ import annotations

from datetime import timedelta

from livekit import api


class LiveKitTokenService:
    def __init__(self, api_key: str, api_secret: str, ttl_seconds: int) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._ttl_seconds = ttl_seconds

    def create_room_token(
        self,
        *,
        room_name: str,
        participant_identity: str,
        display_name: str | None = None,
    ) -> str:
        token = (
            api.AccessToken(self._api_key, self._api_secret)
            .with_identity(participant_identity)
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
            .with_ttl(timedelta(seconds=self._ttl_seconds))
        )
        if display_name:
            token.with_name(display_name)
        return token.to_jwt()
