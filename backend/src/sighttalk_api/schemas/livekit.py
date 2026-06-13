from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

MediaMode = Literal["economy", "balanced", "accurate"]


class MediaPolicy(BaseModel):
    mode: MediaMode
    max_video_fps: float
    max_jpeg_edge: int
    jpeg_quality: int
    vad_enabled: bool


class CreateLiveKitSessionRequest(BaseModel):
    display_name: str | None = None
    media_mode: MediaMode | None = None


class CreateLiveKitSessionResponse(BaseModel):
    room_name: str
    participant_identity: str
    participant_token: str
    livekit_url: str
    expires_at: datetime
    assistant_identity: str
    media_policy: MediaPolicy


class EndLiveKitSessionRequest(BaseModel):
    participant_identity: str


class EndLiveKitSessionResponse(BaseModel):
    status: Literal["ended"]
    room_name: str
