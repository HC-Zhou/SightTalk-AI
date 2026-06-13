from typing import Literal

from pydantic import BaseModel, Field


class ClientEvent(BaseModel):
    type: str


class SessionStartEvent(ClientEvent):
    type: Literal["session.start"]


class SessionStopEvent(ClientEvent):
    type: Literal["session.stop"]


class AudioChunkEvent(ClientEvent):
    type: Literal["audio.chunk"]
    seq: int = Field(ge=0)
    mime: str
    data: str


class VideoFrameEvent(ClientEvent):
    type: Literal["video.frame"]
    seq: int = Field(ge=0)
    mime: str
    captured_at: int = Field(ge=0)
    data: str


class UtteranceEndEvent(ClientEvent):
    type: Literal["utterance.end"]
    audio_seq_end: int = Field(ge=0)


class PlaybackDoneEvent(ClientEvent):
    type: Literal["playback.done"]


class ClientErrorEvent(ClientEvent):
    type: Literal["client.error"]
    stage: str
    message: str


type ParsedClientEvent = (
    SessionStartEvent
    | SessionStopEvent
    | AudioChunkEvent
    | VideoFrameEvent
    | UtteranceEndEvent
    | PlaybackDoneEvent
    | ClientErrorEvent
)

type ClientEventModel = type[ParsedClientEvent]


class CapturePolicy(BaseModel):
    frame_interval_ms: int = 2000
    idle_frame_interval_ms: int = 5000
    image_max_width: int = 640
    jpeg_quality: float = 0.7
    max_keyframes_per_turn: int = 3


class ServerEvent(BaseModel):
    type: str


class SessionReadyEvent(ServerEvent):
    type: Literal["session.ready"] = "session.ready"
    policy: CapturePolicy = Field(default_factory=CapturePolicy)


class PolicyUpdateEvent(ServerEvent):
    type: Literal["policy.update"] = "policy.update"
    policy: CapturePolicy
    reason: str


class TranscriptFinalEvent(ServerEvent):
    type: Literal["transcript.final"] = "transcript.final"
    text: str


class AssistantThinkingEvent(ServerEvent):
    type: Literal["assistant.thinking"] = "assistant.thinking"


class AssistantTextDeltaEvent(ServerEvent):
    type: Literal["assistant.text.delta"] = "assistant.text.delta"
    text: str


class AssistantTextDoneEvent(ServerEvent):
    type: Literal["assistant.text.done"] = "assistant.text.done"
    text: str


class TtsReadyEvent(ServerEvent):
    type: Literal["tts.ready"] = "tts.ready"
    audio_url: str


class CostSnapshotEvent(ServerEvent):
    type: Literal["cost.snapshot"] = "cost.snapshot"
    frames_captured: int
    frames_sent_to_model: int
    asr_calls: int
    vision_llm_calls: int
    tts_calls: int
    policy: str


class ErrorEvent(ServerEvent):
    type: Literal["error"] = "error"
    stage: str
    message: str
    retryable: bool


def parse_client_event(payload: dict[str, object]) -> ParsedClientEvent:
    event_type = payload.get("type")
    if not isinstance(event_type, str):
        raise ValueError(f"Unsupported client event type: {event_type}")

    event_models: dict[str, ClientEventModel] = {
        "session.start": SessionStartEvent,
        "session.stop": SessionStopEvent,
        "audio.chunk": AudioChunkEvent,
        "video.frame": VideoFrameEvent,
        "utterance.end": UtteranceEndEvent,
        "playback.done": PlaybackDoneEvent,
        "client.error": ClientErrorEvent,
    }
    model = event_models.get(event_type)
    if model is None:
        raise ValueError(f"Unsupported client event type: {event_type}")
    return model.model_validate(payload)
