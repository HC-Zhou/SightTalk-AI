import base64
from typing import Any

import httpx

from sighttalk_api.core.config import Settings
from sighttalk_api.media.audio_buffer import AudioChunk
from sighttalk_api.media.frame_buffer import FrameItem

type JsonObject = dict[str, Any]
type AsyncHttpClient = httpx.AsyncClient


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _authorization_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _require_api_key(settings: Settings) -> str:
    if settings.bailian_api_key is None or not settings.bailian_api_key.strip():
        raise ValueError(
            "VISION_ASSISTANT_BAILIAN_API_KEY is required when "
            "VISION_ASSISTANT_AI_PROVIDER=bailian."
        )
    return settings.bailian_api_key


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
