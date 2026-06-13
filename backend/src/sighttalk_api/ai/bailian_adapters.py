import base64
from collections.abc import Awaitable, Mapping
from typing import Any, Protocol

import httpx

from sighttalk_api.ai.adapters import AsrResult
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
