from sighttalk_api.ai.adapters import AsrResult, MultimodalResult, TtsResult
from sighttalk_api.media.audio_buffer import AudioChunk
from sighttalk_api.media.frame_buffer import FrameItem


class MockAsrAdapter:
    def __init__(self, text: str = "What is in the camera view?") -> None:
        self.text = text

    async def transcribe(self, chunks: list[AudioChunk]) -> AsrResult:
        if not chunks:
            return AsrResult(text="")
        return AsrResult(text=self.text)


class MockMultimodalAdapter:
    def __init__(
        self,
        answer: str = "I can see the latest camera frame and answer your question.",
    ) -> None:
        self.answer_text = answer

    async def answer(
        self,
        user_text: str,
        keyframes: list[FrameItem],
        history: list[tuple[str, str]],
    ) -> MultimodalResult:
        if not user_text.strip():
            return MultimodalResult(answer="I did not catch a question. Please try again.")
        if not keyframes:
            return MultimodalResult(answer="I heard you, but I do not have a recent camera frame.")
        return MultimodalResult(answer=self.answer_text)


class MockTtsAdapter:
    def __init__(self, audio_bytes: bytes = b"mock-audio") -> None:
        self.audio_bytes = audio_bytes

    async def synthesize(self, text: str) -> TtsResult:
        return TtsResult(audio_bytes=self.audio_bytes)

