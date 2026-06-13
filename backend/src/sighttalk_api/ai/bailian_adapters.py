import base64
from collections.abc import Awaitable, Mapping
from typing import Any, Protocol

import httpx

from sighttalk_api.ai.adapters import AsrResult, MultimodalResult, TtsResult
from sighttalk_api.core.config import Settings
from sighttalk_api.media.audio_buffer import AudioChunk
from sighttalk_api.media.frame_buffer import FrameItem

type JsonObject = dict[str, Any]


class HttpResponse(Protocol):
    status_code: int
    headers: Mapping[str, str]
    content: bytes

    def raise_for_status(self) -> None: ...

    def json(self) -> JsonObject: ...


class AsyncHttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: JsonObject,
    ) -> Awaitable[HttpResponse]: ...

    def get(self, url: str) -> Awaitable[HttpResponse]: ...


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _authorization_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _require_api_key(settings: Settings) -> str:
    api_key = settings.bailian_api_key.strip() if settings.bailian_api_key else ""
    if not api_key:
        raise ValueError(
            "VISION_ASSISTANT_BAILIAN_API_KEY is required when "
            "VISION_ASSISTANT_AI_PROVIDER=bailian."
        )
    return api_key


def _extract_chat_content(payload: JsonObject) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Bailian chat response missing choices.")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ValueError("Bailian chat response choice must be an object.")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("Bailian chat response missing message.")
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("Bailian chat response message content must be a string.")
    return content.strip()


def _audio_chunks_to_data_url(chunks: list[AudioChunk]) -> str:
    if not chunks:
        raise ValueError("Cannot build audio data URL from empty chunks.")
    mime = chunks[0].mime or "audio/webm"
    audio_bytes = b"".join(base64.b64decode(chunk.data) for chunk in chunks)
    return f"data:{mime};base64,{base64.b64encode(audio_bytes).decode()}"


def _frame_to_image_content(frame: FrameItem) -> JsonObject:
    mime = frame.mime or "image/jpeg"
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:{mime};base64,{frame.data}",
        },
    }


def _audio_mime(format_name: str) -> str:
    if format_name == "mp3":
        return "audio/mpeg"
    if format_name == "pcm":
        return "audio/pcm"
    return f"audio/{format_name}"


def _extract_tts_audio(payload: JsonObject) -> JsonObject:
    output = payload.get("output")
    if not isinstance(output, dict):
        raise ValueError("Bailian TTS response missing output.")
    audio = output.get("audio")
    if not isinstance(audio, dict):
        raise ValueError("Bailian TTS response missing output.audio.")
    return audio


class BailianAsrAdapter:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: AsyncHttpClient | None = None,
    ) -> None:
        self.settings = settings
        self.api_key = _require_api_key(settings)
        self.client = http_client or httpx.AsyncClient(
            timeout=settings.bailian_timeout_seconds
        )

    async def transcribe(self, chunks: list[AudioChunk]) -> AsrResult:
        if not chunks:
            return AsrResult(text="")

        payload = {
            "model": self.settings.bailian_asr_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": _audio_chunks_to_data_url(chunks)},
                        }
                    ],
                }
            ],
            "asr_options": {"enable_itn": False},
        }
        response = await self.client.post(
            _join_url(self.settings.bailian_compatible_base_url, "chat/completions"),
            headers=_authorization_headers(self.api_key),
            json=payload,
        )
        response.raise_for_status()
        return AsrResult(text=_extract_chat_content(response.json()))


class BailianMultimodalAdapter:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: AsyncHttpClient | None = None,
    ) -> None:
        self.settings = settings
        self.api_key = _require_api_key(settings)
        self.client = http_client or httpx.AsyncClient(
            timeout=settings.bailian_timeout_seconds
        )

    async def answer(
        self,
        user_text: str,
        keyframes: list[FrameItem],
        history: list[tuple[str, str]],
    ) -> MultimodalResult:
        if not user_text.strip():
            return MultimodalResult(answer="我没有听清问题，请再说一遍。")
        if not keyframes:
            return MultimodalResult(answer="我听到了问题，但当前没有可用画面。")

        messages: list[JsonObject] = [
            {
                "role": "system",
                "content": (
                    "You are SightTalk AI. Answer in the user's language. "
                    "Use the provided camera frames as visual evidence and keep the "
                    "answer concise."
                ),
            }
        ]
        messages.extend({"role": role, "content": text} for role, text in history)
        user_content: list[JsonObject] = [{"type": "text", "text": user_text}]
        user_content.extend(_frame_to_image_content(frame) for frame in keyframes)
        messages.append({"role": "user", "content": user_content})

        response = await self.client.post(
            _join_url(self.settings.bailian_compatible_base_url, "chat/completions"),
            headers=_authorization_headers(self.api_key),
            json={
                "model": self.settings.bailian_vision_model,
                "messages": messages,
            },
        )
        response.raise_for_status()
        return MultimodalResult(answer=_extract_chat_content(response.json()))


class BailianTtsAdapter:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: AsyncHttpClient | None = None,
    ) -> None:
        self.settings = settings
        self.api_key = _require_api_key(settings)
        self.client = http_client or httpx.AsyncClient(
            timeout=settings.bailian_timeout_seconds
        )

    async def synthesize(self, text: str) -> TtsResult:
        response = await self.client.post(
            self.settings.bailian_tts_endpoint,
            headers=_authorization_headers(self.api_key),
            json={
                "model": self.settings.bailian_tts_model,
                "input": {"text": text},
                "parameters": {
                    "voice": self.settings.bailian_tts_voice,
                    "format": self.settings.bailian_tts_format,
                    "sample_rate": self.settings.bailian_tts_sample_rate,
                },
            },
        )
        response.raise_for_status()
        audio = _extract_tts_audio(response.json())
        mime = _audio_mime(self.settings.bailian_tts_format)

        audio_data = audio.get("data")
        if isinstance(audio_data, str) and audio_data:
            return TtsResult(audio_bytes=base64.b64decode(audio_data), mime=mime)

        audio_url = audio.get("url")
        if isinstance(audio_url, str) and audio_url:
            download = await self.client.get(audio_url)
            download.raise_for_status()
            return TtsResult(audio_bytes=download.content, mime=mime)

        raise ValueError("Bailian TTS response missing audio data or audio url.")
