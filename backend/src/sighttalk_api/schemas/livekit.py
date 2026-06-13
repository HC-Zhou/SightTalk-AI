"""LiveKit session API schemas shared by backend and frontend contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

MediaMode = Literal["economy", "balanced", "accurate"]


class MediaPolicy(BaseModel):
    """Backend camera/audio policy returned to the browser for visibility."""

    mode: MediaMode
    max_video_fps: float
    max_jpeg_edge: int
    jpeg_quality: int
    vad_enabled: bool


class CreateLiveKitSessionRequest(BaseModel):
    """Request body for creating a browser participant LiveKit session."""

    display_name: str | None = None
    media_mode: MediaMode | None = None


class CreateLiveKitSessionResponse(BaseModel):
    """LiveKit join data and assistant session metadata."""

    room_name: str
    participant_identity: str
    participant_token: str
    livekit_url: str
    expires_at: datetime
    assistant_identity: str
    media_policy: MediaPolicy


class EndLiveKitSessionRequest(BaseModel):
    """Request body for ending a user-owned LiveKit session."""

    participant_identity: str


class EndLiveKitSessionResponse(BaseModel):
    """Idempotent session end response."""

    status: Literal["ended"]
    room_name: str
