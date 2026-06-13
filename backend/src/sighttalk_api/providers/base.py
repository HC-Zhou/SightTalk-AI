"""Provider-neutral contracts for realtime AI services."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class ProviderSessionConfig:
    """Immutable configuration required to open a provider session."""

    session_id: str
    model: str
    workspace_id: str
    system_prompt: str


@dataclass(frozen=True)
class ProviderContext:
    """Provider-ready prompt/context update for manual response flows."""

    system_prompt: str


@dataclass(frozen=True)
class ProviderCapabilities:
    """Feature flags exposed by provider adapters."""

    supports_manual_response: bool = False
    supports_context_update: bool = False


@dataclass(frozen=True)
class AudioChunk:
    """Provider-ready microphone audio chunk."""

    data: bytes
    sample_rate: int
    mime_type: str = "audio/pcm"


@dataclass(frozen=True)
class ImageFrame:
    """Provider-ready camera frame after backend sampling and JPEG encoding."""

    data: bytes
    mime_type: str
    width: int
    height: int


@dataclass(frozen=True)
class ControlEvent:
    """Provider-neutral control command from the frontend."""

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
    """Normalized event emitted by provider adapters."""

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
    """Realtime AI provider interface used by the agent layer."""

    def capabilities(self) -> ProviderCapabilities:
        raise NotImplementedError

    async def connect(self, session: ProviderSessionConfig) -> None:
        raise NotImplementedError

    async def update_context(self, context: ProviderContext) -> None:
        raise NotImplementedError

    async def create_response(self) -> None:
        raise NotImplementedError

    async def send_audio(self, chunk: AudioChunk) -> None:
        raise NotImplementedError

    async def send_image(self, frame: ImageFrame) -> bool:
        raise NotImplementedError

    async def send_control(self, event: ControlEvent) -> None:
        raise NotImplementedError

    def events(self) -> AsyncIterator[ProviderEvent]:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError
