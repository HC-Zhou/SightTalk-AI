from dataclasses import dataclass

from sighttalk_api.core.events import CapturePolicy, CostSnapshotEvent, PolicyUpdateEvent


@dataclass
class CostState:
    frames_captured: int = 0
    frames_received: int = 0
    frames_sent_to_model: int = 0
    asr_calls: int = 0
    multimodal_calls: int = 0
    tts_calls: int = 0

    def record_frame_captured(self) -> None:
        self.frames_captured += 1

    def record_frame_received(self) -> None:
        self.frames_received += 1

    def record_frames_sent_to_model(self, count: int) -> None:
        self.frames_sent_to_model += count

    def record_asr_call(self) -> None:
        self.asr_calls += 1

    def record_multimodal_call(self) -> None:
        self.multimodal_calls += 1

    def record_tts_call(self) -> None:
        self.tts_calls += 1

    def to_snapshot(self, policy_name: str) -> CostSnapshotEvent:
        return CostSnapshotEvent(
            frames_captured=self.frames_captured,
            frames_sent_to_model=self.frames_sent_to_model,
            asr_calls=self.asr_calls,
            vision_llm_calls=self.multimodal_calls,
            tts_calls=self.tts_calls,
            policy=policy_name,
        )


class CostController:
    def __init__(self) -> None:
        self.policy = CapturePolicy()
        self.policy_name = "normal"

    def downgrade(self, reason: str) -> PolicyUpdateEvent:
        self.policy_name = "degraded"
        self.policy = CapturePolicy(
            frame_interval_ms=4000,
            idle_frame_interval_ms=8000,
            image_max_width=480,
            jpeg_quality=0.55,
            max_keyframes_per_turn=2,
        )
        return PolicyUpdateEvent(policy=self.policy, reason=reason)
