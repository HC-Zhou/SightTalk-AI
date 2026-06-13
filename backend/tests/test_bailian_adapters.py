import base64
from collections.abc import Mapping
from typing import Any

from sighttalk_api.ai.bailian_adapters import (
    AsyncHttpClient,
    BailianAsrAdapter,
    BailianMultimodalAdapter,
    BailianTtsAdapter,
    HttpResponse,
    _audio_chunks_to_data_url,
    _extract_chat_content,
    _join_url,
    _require_api_key,
)
from sighttalk_api.core.config import Settings
from sighttalk_api.media.audio_buffer import AudioChunk
from sighttalk_api.media.frame_buffer import FrameItem


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


async def test_bailian_asr_returns_empty_text_for_empty_chunks() -> None:
    adapter = BailianAsrAdapter(
        Settings(ai_provider="bailian", bailian_api_key="sk-test")
    )

    result = await adapter.transcribe([])

    assert result.text == ""


async def test_bailian_asr_posts_audio_data_url() -> None:
    client = FakeAsyncClient(
        [FakeResponse({"choices": [{"message": {"content": "打开摄像头"}}]})]
    )
    adapter = BailianAsrAdapter(
        Settings(ai_provider="bailian", bailian_api_key="sk-test"),
        http_client=client,
    )

    result = await adapter.transcribe(
        [AudioChunk(seq=1, mime="audio/webm", data=base64.b64encode(b"audio").decode())]
    )

    assert result.text == "打开摄像头"
    assert client.posts[0]["url"] == (
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    )
    assert client.posts[0]["headers"]["Authorization"] == "Bearer sk-test"
    body = client.posts[0]["json"]
    assert body["model"] == "qwen3-asr-flash"
    assert body["asr_options"] == {"enable_itn": False}
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["content"][0]["type"] == "input_audio"
    assert body["messages"][0]["content"][0]["input_audio"]["data"].startswith(
        "data:audio/webm;base64,"
    )


async def test_bailian_multimodal_posts_text_history_and_images() -> None:
    client = FakeAsyncClient(
        [FakeResponse({"choices": [{"message": {"content": "画面里有一台电脑。"}}]})]
    )
    adapter = BailianMultimodalAdapter(
        Settings(ai_provider="bailian", bailian_api_key="sk-test"),
        http_client=client,
    )

    result = await adapter.answer(
        "看到了什么？",
        [
            FrameItem(
                seq=7,
                captured_at=1710000000000,
                mime="image/jpeg",
                data=base64.b64encode(b"frame").decode(),
                width=640,
                height=480,
            )
        ],
        [("user", "你好"), ("assistant", "你好，我在。")],
    )

    assert result.answer == "画面里有一台电脑。"
    body = client.posts[0]["json"]
    assert body["model"] == "qwen3.5-plus"
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1] == {"role": "user", "content": "你好"}
    assert body["messages"][2] == {"role": "assistant", "content": "你好，我在。"}
    user_message = body["messages"][3]
    assert user_message["role"] == "user"
    assert user_message["content"][0] == {
        "type": "text",
        "text": "看到了什么？",
    }
    assert user_message["content"][1]["type"] == "image_url"
    assert user_message["content"][1]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,"
    )


async def test_bailian_multimodal_returns_fallback_for_blank_user_text() -> None:
    client = FakeAsyncClient([])
    adapter = BailianMultimodalAdapter(
        Settings(ai_provider="bailian", bailian_api_key="sk-test"),
        http_client=client,
    )

    result = await adapter.answer(
        "   ",
        [
            FrameItem(
                seq=7,
                captured_at=1710000000000,
                mime="image/jpeg",
                data=base64.b64encode(b"frame").decode(),
                width=640,
                height=480,
            )
        ],
        [],
    )

    assert result.answer == "我没有听清问题，请再说一遍。"
    assert client.posts == []


async def test_bailian_multimodal_returns_fallback_without_keyframes() -> None:
    client = FakeAsyncClient([])
    adapter = BailianMultimodalAdapter(
        Settings(ai_provider="bailian", bailian_api_key="sk-test"),
        http_client=client,
    )

    result = await adapter.answer("看到了什么？", [], [])

    assert result.answer == "我听到了问题，但当前没有可用画面。"
    assert client.posts == []


async def test_bailian_tts_decodes_inline_audio_data() -> None:
    audio_data = base64.b64encode(b"wav-bytes").decode()
    client = FakeAsyncClient([FakeResponse({"output": {"audio": {"data": audio_data}}})])
    adapter = BailianTtsAdapter(
        Settings(ai_provider="bailian", bailian_api_key="sk-test"),
        http_client=client,
    )

    result = await adapter.synthesize("你好")

    assert result.audio_bytes == b"wav-bytes"
    assert result.mime == "audio/wav"
    body = client.posts[0]["json"]
    assert body == {
        "model": "cosyvoice-v3-flash",
        "input": {"text": "你好"},
        "parameters": {
            "voice": "longanyang",
            "format": "wav",
            "sample_rate": 24000,
        },
    }


async def test_bailian_tts_downloads_audio_url() -> None:
    client = FakeAsyncClient(
        [
            FakeResponse({"output": {"audio": {"url": "https://example.com/audio.wav"}}}),
            FakeResponse(b"downloaded-wav", content_type="audio/wav"),
        ]
    )
    adapter = BailianTtsAdapter(
        Settings(ai_provider="bailian", bailian_api_key="sk-test"),
        http_client=client,
    )

    result = await adapter.synthesize("你好")

    assert client.gets == ["https://example.com/audio.wav"]
    assert result.audio_bytes == b"downloaded-wav"
    assert result.mime == "audio/wav"
