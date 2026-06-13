from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class ProviderSessionConfig:
    session_id: str
    model: str
    workspace_id: str
    system_prompt: str


@dataclass(frozen=True)
class AudioChunk:
    data: bytes
    sample_rate: int
    mime_type: str = "audio/pcm"


@dataclass(frozen=True)
class ImageFrame:
    data: bytes
    mime_type: str
    width: int
    height: int


@dataclass(frozen=True)
class ControlEvent:
    type: Literal["interrupt", "mode_update"]
    value: str | None = None


ProviderEventType = Literal[
    "status",
    "transcript_delta",
    "transcript_done",
    "response_done",
    "audio_delta",
    "audio",
    "error",
]


@dataclass(frozen=True)
class ProviderEvent:
    type: ProviderEventType
    text: str = ""
    speaker: Literal["user", "assistant"] = "assistant"
    message_id: str = ""
    status: str = ""
    audio: bytes = b""
    mime_type: str = "audio/pcm"
    code: str = ""
    message: str = ""


class AIProvider(Protocol):
    async def connect(self, session: ProviderSessionConfig) -> None:
        raise NotImplementedError

    async def send_audio(self, chunk: AudioChunk) -> None:
        raise NotImplementedError

    async def send_image(self, frame: ImageFrame) -> None:
        raise NotImplementedError

    async def send_control(self, event: ControlEvent) -> None:
        raise NotImplementedError

    def events(self) -> AsyncIterator[ProviderEvent]:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError
