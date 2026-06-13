import base64
from collections.abc import Mapping
from typing import Any

from sighttalk_api.ai.bailian_adapters import (
    AsyncHttpClient,
    HttpResponse,
    _audio_chunks_to_data_url,
    _extract_chat_content,
    _join_url,
    _require_api_key,
)
from sighttalk_api.core.config import Settings
from sighttalk_api.media.audio_buffer import AudioChunk


class FakeResponse:
    def __init__(
        self,
        payload: dict[str, Any] | bytes,
        *,
        status_code: int = 200,
        content_type: str = "application/json",
    ) -> None:
        self.payload: dict[str, Any] | bytes = payload
        self.status_code: int = status_code
        self.headers: Mapping[str, str] = {"content-type": content_type}
        self.content: bytes = payload if isinstance(payload, bytes) else b""

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        if isinstance(self.payload, bytes):
            raise ValueError("binary response has no json")
        return self.payload


class FakeAsyncClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.posts: list[dict[str, Any]] = []
        self.gets: list[str] = []

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> HttpResponse:
        self.posts.append({"url": url, "headers": headers, "json": json})
        return self.responses.pop(0)

    async def get(self, url: str) -> HttpResponse:
        self.gets.append(url)
        return self.responses.pop(0)


def test_join_url_handles_slashes() -> None:
    assert _join_url(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/",
        "chat/completions",
    ) == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def test_extract_chat_content_reads_first_choice() -> None:
    payload = {"choices": [{"message": {"content": "你好"}}]}

    assert _extract_chat_content(payload) == "你好"


def test_require_api_key_returns_stripped_key() -> None:
    settings = Settings(bailian_api_key="  sk-test  ")

    assert _require_api_key(settings) == "sk-test"


def test_fake_async_client_matches_async_http_client_protocol() -> None:
    fake = FakeAsyncClient([FakeResponse({})])
    client: AsyncHttpClient = fake

    assert client is fake
    assert fake.gets == []


def test_audio_chunks_to_data_url_joins_base64_payloads() -> None:
    chunks = [
        AudioChunk(seq=1, mime="audio/webm", data=base64.b64encode(b"hello").decode()),
        AudioChunk(seq=2, mime="audio/webm", data=base64.b64encode(b" world").decode()),
    ]

    assert _audio_chunks_to_data_url(chunks) == (
        "data:audio/webm;base64," + base64.b64encode(b"hello world").decode()
    )
