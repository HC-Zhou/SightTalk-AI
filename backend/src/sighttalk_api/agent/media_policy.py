from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from sighttalk_api.schemas.livekit import MediaMode, MediaPolicy


@dataclass
class FrameBudget:
    policy: MediaPolicy
    last_frame_at: float = 0.0
    frames_sent: int = 0

    def can_send_frame(
        self,
        *,
        now: float | None = None,
        explicit_visual_request: bool = False,
    ) -> bool:
        if explicit_visual_request:
            return True
        if self.policy.max_video_fps <= 0:
            return False
        current = monotonic() if now is None else now
        min_interval = 1.0 / self.policy.max_video_fps
        return current - self.last_frame_at >= min_interval

    def mark_sent(self, *, now: float | None = None) -> None:
        self.last_frame_at = monotonic() if now is None else now
        self.frames_sent += 1


def is_visual_request(text: str) -> bool:
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
    fps = {
        "economy": min(base.max_video_fps, 0.2),
        "balanced": max(base.max_video_fps, 1.0),
        "accurate": max(base.max_video_fps, 2.0),
    }[mode]
    return MediaPolicy(
        mode=mode,
        max_video_fps=fps,
        max_jpeg_edge=base.max_jpeg_edge,
        jpeg_quality=base.jpeg_quality,
        vad_enabled=base.vad_enabled,
    )
