from dataclasses import dataclass
from typing import Protocol

from sighttalk_api.media.audio_buffer import AudioChunk
from sighttalk_api.media.frame_buffer import FrameItem


@dataclass(frozen=True)
class AsrResult:
    text: str


@dataclass(frozen=True)
class MultimodalResult:
    answer: str


@dataclass(frozen=True)
class TtsResult:
    audio_bytes: bytes
    mime: str = "audio/wav"


class AsrAdapter(Protocol):
    async def transcribe(self, chunks: list[AudioChunk]) -> AsrResult: ...


class MultimodalAdapter(Protocol):
    async def answer(
        self,
        user_text: str,
        keyframes: list[FrameItem],
        history: list[tuple[str, str]],
    ) -> MultimodalResult: ...


class TtsAdapter(Protocol):
    async def synthesize(self, text: str) -> TtsResult: ...

