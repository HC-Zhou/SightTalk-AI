"""Camera frame budgeting and media-mode policy helpers."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from sighttalk_api.schemas.livekit import MediaMode, MediaPolicy


@dataclass
class FrameBudget:
    """Tracks whether a camera frame can be sent under a fixed FPS policy."""

    policy: MediaPolicy
    last_frame_at: float = 0.0
    frames_sent: int = 0

    def can_send_frame(
        self,
        *,
        now: float | None = None,
        explicit_visual_request: bool = False,
    ) -> bool:
        """Return whether sending a frame is allowed at the current time."""
        if explicit_visual_request:
            return True
        if self.policy.max_video_fps <= 0:
            return False
        current = monotonic() if now is None else now
        min_interval = 1.0 / self.policy.max_video_fps
        return current - self.last_frame_at >= min_interval

    def mark_sent(self, *, now: float | None = None) -> None:
        """Record a successful frame send for future budget checks."""
        self.last_frame_at = monotonic() if now is None else now
        self.frames_sent += 1


def is_visual_request(text: str) -> bool:
    """Detect whether user text explicitly asks about visual context."""
    normalized = text.lower()
    keywords = (
        "see",
        "look",
        "camera",
        "visible",
        "read",
        "看",
        "看到",
        "画面",
        "摄像头",
        "读",
    )
    return any(keyword in normalized for keyword in keywords)


def derive_mode_policy(base: MediaPolicy, mode: MediaMode) -> MediaPolicy:
    """Return a media policy adjusted for economy, balanced, or accurate mode."""
    fps = {
        "economy": min(base.max_video_fps, 0.2),
        "balanced": 0.5,
        "accurate": 1.0,
    }[mode]
    return MediaPolicy(
        mode=mode,
        max_video_fps=fps,
        max_jpeg_edge=base.max_jpeg_edge,
        jpeg_quality=base.jpeg_quality,
        vad_enabled=base.vad_enabled,
    )
