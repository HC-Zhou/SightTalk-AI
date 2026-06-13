from sighttalk_api.core.cost import CostController, CostState
from sighttalk_api.core.events import CapturePolicy


def test_default_policy_matches_mvp_limits() -> None:
    controller = CostController()

    assert controller.policy == CapturePolicy(
        frame_interval_ms=2000,
        idle_frame_interval_ms=5000,
        image_max_width=640,
        jpeg_quality=0.7,
        max_keyframes_per_turn=3,
    )


def test_cost_state_tracks_model_calls() -> None:
    state = CostState()
    state.record_frame_captured()
    state.record_frame_received()
    state.record_frames_sent_to_model(3)
    state.record_asr_call()
    state.record_multimodal_call()
    state.record_tts_call()

    snapshot = state.to_snapshot(policy_name="normal")

    assert snapshot.frames_captured == 1
    assert snapshot.frames_sent_to_model == 3
    assert snapshot.asr_calls == 1
    assert snapshot.vision_llm_calls == 1
    assert snapshot.tts_calls == 1
    assert snapshot.policy == "normal"


def test_policy_downgrade_increases_intervals_and_lowers_quality() -> None:
    controller = CostController()

    event = controller.downgrade(reason="queue pressure")

    assert event.type == "policy.update"
    assert event.reason == "queue pressure"
    assert event.policy.frame_interval_ms == 4000
    assert event.policy.idle_frame_interval_ms == 8000
    assert event.policy.jpeg_quality == 0.55
    assert controller.policy == event.policy
