from __future__ import annotations

from sighttalk_api.agent.media_policy import FrameBudget, derive_mode_policy, is_visual_request
from sighttalk_api.schemas.livekit import MediaPolicy


def test_frame_budget_limits_by_fps() -> None:
    budget = FrameBudget(
        MediaPolicy(
            mode="balanced",
            max_video_fps=1.0,
            max_jpeg_edge=1024,
            jpeg_quality=75,
            vad_enabled=True,
        )
    )

    assert budget.can_send_frame(now=2.0)
    budget.mark_sent(now=2.0)
    assert not budget.can_send_frame(now=2.2)
    assert budget.can_send_frame(now=3.1)


def test_visual_request_keywords() -> None:
    assert is_visual_request("Can you read what is on the screen?")
    assert is_visual_request("你能看到摄像头里的内容吗")
    assert not is_visual_request("Tell me a short joke")


def test_derive_mode_policy_changes_fps() -> None:
    base = MediaPolicy(
        mode="balanced",
        max_video_fps=1.0,
        max_jpeg_edge=1024,
        jpeg_quality=75,
        vad_enabled=True,
    )

    assert derive_mode_policy(base, "economy").max_video_fps == 0.2
    assert derive_mode_policy(base, "balanced").max_video_fps == 0.5
    assert derive_mode_policy(base, "accurate").max_video_fps == 1.0
