# Alibaba Bailian Provider Integration Implementation Plan

This plan is written for agentic workers. Each task is scoped so a worker can execute it from the repository root, verify it with explicit commands, and commit only the files listed in that task.

## Goal

接入阿里云百炼平台作为真实 AI provider，使后端在 `VISION_ASSISTANT_AI_PROVIDER=bailian` 时调用百炼完成语音识别、视觉问答和语音合成，同时保留默认 `mock` provider 以保证本地演示稳定。

验收标准：

- 默认不配置密钥时仍使用 mock provider，现有测试和本地 demo 行为不变。
- 配置 `VISION_ASSISTANT_AI_PROVIDER=bailian` 和 `VISION_ASSISTANT_BAILIAN_API_KEY` 后，后端 provider factory 返回百炼 ASR、视觉问答、TTS 三个适配器。
- 百炼 ASR 使用 OpenAI 兼容 Chat Completions HTTP 接口和 `qwen3-asr-flash` 模型处理前端上传的音频 Data URL。
- 百炼视觉问答使用 OpenAI 兼容 Chat Completions HTTP 接口和可配置多模态模型处理用户文本、历史对话、关键帧 Data URL。
- 百炼 TTS 使用 CosyVoice 非实时 HTTP 接口生成音频，并兼容返回音频 URL 或 base64 音频数据两种响应。
- 所有新增逻辑有单元测试覆盖，测试不调用真实百炼服务。
- README、`backend/.env.example`、`compose.yaml` 说明并暴露百炼配置，但不提交任何真实密钥。

## Architecture

现有后端已经有稳定的 adapter 边界：

- `backend/src/sighttalk_api/ai/adapters.py` 定义 `AsrAdapter`、`MultimodalAdapter`、`TtsAdapter` 协议。
- `backend/src/sighttalk_api/ai/orchestrator.py` 只依赖协议，不关心 provider 细节。
- `backend/src/sighttalk_api/ai/provider_adapters.py` 负责根据配置创建 provider 实例。

本次接入沿用该边界，新增 `backend/src/sighttalk_api/ai/bailian_adapters.py`，把百炼 HTTP 请求、响应解析、错误处理和 Data URL 组装全部限制在该文件内。`DialogueOrchestrator`、WebSocket 路由和前端不需要改动。

数据流：

```text
Browser audio chunks + sampled camera frames
  -> WebSocket session buffers
  -> DialogueOrchestrator
  -> BailianAsrAdapter.transcribe()
  -> BailianMultimodalAdapter.answer()
  -> BailianTtsAdapter.synthesize()
  -> InMemoryAudioStore
  -> TtsReadyEvent(audio_url)
```

百炼接口选型：

- ASR：OpenAI 兼容 `POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`，模型默认 `qwen3-asr-flash`。
- 视觉问答：OpenAI 兼容 `POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`，模型默认 `qwen3.5-plus`。
- TTS：CosyVoice 非实时 HTTP `POST https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer`，模型默认 `cosyvoice-v3-flash`。

## Tech Stack

- Python 3.14
- FastAPI
- Pydantic Settings
- `httpx.AsyncClient`
- Pytest and pytest-asyncio
- Ruff and MyPy strict mode
- Docker Compose
- Alibaba Cloud Model Studio / Bailian OpenAI-compatible API
- Alibaba Cloud Model Studio / Bailian CosyVoice HTTP API

---

## Source References

- 百炼 OpenAI 兼容接口文档：<https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope>
- 百炼视觉理解文档：<https://www.alibabacloud.com/help/en/model-studio/vision>
- Qwen-ASR API 文档：<https://help.aliyun.com/zh/model-studio/qwen-asr-api-reference>
- CosyVoice TTS HTTP API 文档：<https://help.aliyun.com/zh/model-studio/cosyvoice-tts-http-api>

## Scope Check

本计划只接入百炼到当前“一次用户发言结束后处理一轮”的管线。它不改前端采集方式，不引入实时双向音频流，不接入 WebRTC，也不替换现有 mock provider。若后续需要 Qwen-Omni 实时语音视觉对话，应单独开分支和 PR。

## File Structure

需要新增或修改的文件：

```text
backend/pyproject.toml
backend/uv.lock
backend/.env.example
backend/src/sighttalk_api/core/config.py
backend/src/sighttalk_api/ai/bailian_adapters.py
backend/src/sighttalk_api/ai/provider_adapters.py
backend/tests/test_bailian_config.py
backend/tests/test_bailian_adapters.py
backend/tests/test_provider_config.py
compose.yaml
README.md
```

## Task 1: Add Bailian configuration and runtime dependency

目标：让应用可以通过环境变量完整配置百炼 provider，并把 `httpx` 从开发依赖提升为运行依赖。

先写测试：新增 `backend/tests/test_bailian_config.py`。

```python
from sighttalk_api.core.config import Settings


def test_bailian_defaults_are_available() -> None:
    settings = Settings()

    assert settings.bailian_api_key is None
    assert settings.bailian_compatible_base_url == (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    assert settings.bailian_asr_model == "qwen3-asr-flash"
    assert settings.bailian_vision_model == "qwen3.5-plus"
    assert settings.bailian_tts_endpoint == (
        "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer"
    )
    assert settings.bailian_tts_model == "cosyvoice-v3-flash"
    assert settings.bailian_tts_voice == "longanyang"
    assert settings.bailian_tts_format == "wav"
    assert settings.bailian_tts_sample_rate == 24000
    assert settings.bailian_timeout_seconds == 30.0


def test_bailian_settings_can_be_constructed_explicitly() -> None:
    settings = Settings(
        ai_provider="bailian",
        bailian_api_key="sk-test",
        bailian_vision_model="qwen-vl-plus",
        bailian_tts_voice="longcheng",
    )

    assert settings.ai_provider == "bailian"
    assert settings.bailian_api_key == "sk-test"
    assert settings.bailian_vision_model == "qwen-vl-plus"
    assert settings.bailian_tts_voice == "longcheng"
```

修改 `backend/src/sighttalk_api/core/config.py`，在 `Settings` 中追加字段：

```python
bailian_api_key: str | None = Field(default=None)
bailian_compatible_base_url: str = Field(
    default="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
bailian_asr_model: str = Field(default="qwen3-asr-flash")
bailian_vision_model: str = Field(default="qwen3.5-plus")
bailian_tts_endpoint: str = Field(
    default="https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer"
)
bailian_tts_model: str = Field(default="cosyvoice-v3-flash")
bailian_tts_voice: str = Field(default="longanyang")
bailian_tts_format: str = Field(default="wav")
bailian_tts_sample_rate: int = Field(default=24000)
bailian_timeout_seconds: float = Field(default=30.0)
```

修改 `backend/pyproject.toml`：

- 在 `[project].dependencies` 加入 `"httpx>=0.28.1"`。
- 从 `[dependency-groups].dev` 删除 `"httpx>=0.28.1"`，避免运行依赖和开发依赖重复声明。

更新锁文件：

```bash
cd backend
uv sync --dev
```

验证命令：

```bash
cd backend
uv run pytest tests/test_bailian_config.py -v
uv run ruff check src/sighttalk_api/core/config.py tests/test_bailian_config.py
uv run mypy
```

预期结果：

```text
tests/test_bailian_config.py::test_bailian_defaults_are_available PASSED
tests/test_bailian_config.py::test_bailian_settings_can_be_constructed_explicitly PASSED
All checks passed!
Success: no issues found in 1 source file
```

提交：

```bash
git add backend/pyproject.toml backend/uv.lock backend/src/sighttalk_api/core/config.py backend/tests/test_bailian_config.py
git commit -m "feat(config): 新增百炼服务配置"
```

## Task 2: Add shared Bailian HTTP helpers

目标：创建百炼适配器文件，先实现可单测的 URL、鉴权、响应解析和 Data URL 组装工具。

新增 `backend/tests/test_bailian_adapters.py`，先放入测试辅助类：

```python
import base64
from typing import Any

from sighttalk_api.ai.bailian_adapters import (
    _audio_chunks_to_data_url,
    _extract_chat_content,
    _join_url,
)
from sighttalk_api.media.audio_buffer import AudioChunk


class FakeResponse:
    def __init__(
        self,
        payload: dict[str, Any] | bytes,
        *,
        status_code: int = 200,
        content_type: str = "application/json",
    ) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self.content = payload if isinstance(payload, bytes) else b""

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
    ) -> FakeResponse:
        self.posts.append({"url": url, "headers": headers, "json": json})
        return self.responses.pop(0)

    async def get(self, url: str) -> FakeResponse:
        self.gets.append(url)
        return self.responses.pop(0)
```

继续写 helper 测试：

```python
def test_join_url_handles_slashes() -> None:
    assert _join_url("https://dashscope.aliyuncs.com/compatible-mode/v1/", "chat/completions") == (
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    )


def test_extract_chat_content_reads_first_choice() -> None:
    payload = {"choices": [{"message": {"content": "你好"}}]}

    assert _extract_chat_content(payload) == "你好"


def test_audio_chunks_to_data_url_joins_base64_payloads() -> None:
    chunks = [
        AudioChunk(seq=1, mime="audio/webm", data=base64.b64encode(b"hello").decode()),
        AudioChunk(seq=2, mime="audio/webm", data=base64.b64encode(b" world").decode()),
    ]

    assert _audio_chunks_to_data_url(chunks) == (
        "data:audio/webm;base64," + base64.b64encode(b"hello world").decode()
    )
```

新增 `backend/src/sighttalk_api/ai/bailian_adapters.py`：

```python
import base64
from typing import Any

import httpx

from sighttalk_api.ai.adapters import AsrResult, MultimodalResult, TtsResult
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
```

验证命令：

```bash
cd backend
uv run pytest tests/test_bailian_adapters.py -v
uv run ruff check src/sighttalk_api/ai/bailian_adapters.py tests/test_bailian_adapters.py
uv run mypy
```

预期结果：

```text
tests/test_bailian_adapters.py::test_join_url_handles_slashes PASSED
tests/test_bailian_adapters.py::test_extract_chat_content_reads_first_choice PASSED
tests/test_bailian_adapters.py::test_audio_chunks_to_data_url_joins_base64_payloads PASSED
All checks passed!
Success: no issues found in 1 source file
```

提交：

```bash
git add backend/src/sighttalk_api/ai/bailian_adapters.py backend/tests/test_bailian_adapters.py
git commit -m "feat(ai): 新增百炼适配器基础工具"
```

## Task 3: Implement Bailian ASR adapter

目标：实现语音识别适配器，空音频保持当前 mock 语义，非空音频调用百炼兼容 Chat Completions。

在 `backend/tests/test_bailian_adapters.py` 追加测试：

```python
from sighttalk_api.ai.bailian_adapters import BailianAsrAdapter
from sighttalk_api.core.config import Settings


async def test_bailian_asr_returns_empty_text_for_empty_chunks() -> None:
    adapter = BailianAsrAdapter(Settings(ai_provider="bailian", bailian_api_key="sk-test"))

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
```

在 `backend/src/sighttalk_api/ai/bailian_adapters.py` 追加：

```python
class BailianAsrAdapter:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: AsyncHttpClient | None = None,
    ) -> None:
        self.settings = settings
        self.api_key = _require_api_key(settings)
        self.client = http_client or httpx.AsyncClient(timeout=settings.bailian_timeout_seconds)

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
```

注意：当前前端上传浏览器编码后的 `audio/webm` 片段。计划内不新增音频转码。如果百炼模型在真实联调中拒绝该 mime，后续应单独实现服务端转码或调整前端采集编码，不在本 PR 混入。

验证命令：

```bash
cd backend
uv run pytest tests/test_bailian_adapters.py -v
uv run ruff check src/sighttalk_api/ai/bailian_adapters.py tests/test_bailian_adapters.py
uv run mypy
```

提交：

```bash
git add backend/src/sighttalk_api/ai/bailian_adapters.py backend/tests/test_bailian_adapters.py
git commit -m "feat(ai): 接入百炼语音识别"
```

## Task 4: Implement Bailian multimodal adapter

目标：实现视觉问答适配器，把历史对话、用户文本和关键帧组织为百炼兼容多模态消息。

在 `backend/tests/test_bailian_adapters.py` 追加测试：

```python
from sighttalk_api.ai.bailian_adapters import BailianMultimodalAdapter
from sighttalk_api.media.frame_buffer import FrameItem


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
```

在 `backend/src/sighttalk_api/ai/bailian_adapters.py` 追加：

```python
class BailianMultimodalAdapter:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: AsyncHttpClient | None = None,
    ) -> None:
        self.settings = settings
        self.api_key = _require_api_key(settings)
        self.client = http_client or httpx.AsyncClient(timeout=settings.bailian_timeout_seconds)

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
                    "Use the provided camera frames as visual evidence and keep the answer concise."
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
```

验证命令：

```bash
cd backend
uv run pytest tests/test_bailian_adapters.py -v
uv run ruff check src/sighttalk_api/ai/bailian_adapters.py tests/test_bailian_adapters.py
uv run mypy
```

提交：

```bash
git add backend/src/sighttalk_api/ai/bailian_adapters.py backend/tests/test_bailian_adapters.py
git commit -m "feat(ai): 接入百炼视觉问答"
```

## Task 5: Implement Bailian TTS adapter

目标：实现 CosyVoice 非实时 TTS，支持 `output.audio.data` 的 base64 音频和 `output.audio.url` 的下载音频。

在 `backend/tests/test_bailian_adapters.py` 追加测试：

```python
from sighttalk_api.ai.bailian_adapters import BailianTtsAdapter


async def test_bailian_tts_decodes_inline_audio_data() -> None:
    audio_data = base64.b64encode(b"wav-bytes").decode()
    client = FakeAsyncClient(
        [FakeResponse({"output": {"audio": {"data": audio_data}}})]
    )
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
```

在 `backend/src/sighttalk_api/ai/bailian_adapters.py` 追加：

```python
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


class BailianTtsAdapter:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: AsyncHttpClient | None = None,
    ) -> None:
        self.settings = settings
        self.api_key = _require_api_key(settings)
        self.client = http_client or httpx.AsyncClient(timeout=settings.bailian_timeout_seconds)

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
```

验证命令：

```bash
cd backend
uv run pytest tests/test_bailian_adapters.py -v
uv run ruff check src/sighttalk_api/ai/bailian_adapters.py tests/test_bailian_adapters.py
uv run mypy
```

提交：

```bash
git add backend/src/sighttalk_api/ai/bailian_adapters.py backend/tests/test_bailian_adapters.py
git commit -m "feat(ai): 接入百炼语音合成"
```

## Task 6: Wire provider factory

目标：让 `build_adapters()` 支持 `mock` 和 `bailian` 两种 provider，并在配置错误时给出明确异常。

修改 `backend/tests/test_provider_config.py`：

```python
import pytest

from sighttalk_api.ai.provider_adapters import build_adapters
from sighttalk_api.core.config import Settings


def test_default_settings_use_mock_provider() -> None:
    settings = Settings()

    assert settings.ai_provider == "mock"
    assert settings.asr_api_url is None
    assert settings.multimodal_api_url is None
    assert settings.tts_api_url is None
    assert settings.bailian_api_key is None


def test_build_adapters_returns_mock_adapters_by_default() -> None:
    asr, multimodal, tts = build_adapters(Settings(ai_provider="mock"))

    assert asr.__class__.__name__ == "MockAsrAdapter"
    assert multimodal.__class__.__name__ == "MockMultimodalAdapter"
    assert tts.__class__.__name__ == "MockTtsAdapter"


def test_build_adapters_returns_bailian_adapters() -> None:
    asr, multimodal, tts = build_adapters(
        Settings(ai_provider="bailian", bailian_api_key="sk-test")
    )

    assert asr.__class__.__name__ == "BailianAsrAdapter"
    assert multimodal.__class__.__name__ == "BailianMultimodalAdapter"
    assert tts.__class__.__name__ == "BailianTtsAdapter"


def test_build_bailian_adapters_requires_api_key() -> None:
    with pytest.raises(ValueError, match="VISION_ASSISTANT_BAILIAN_API_KEY"):
        build_adapters(Settings(ai_provider="bailian"))
```

修改 `backend/src/sighttalk_api/ai/provider_adapters.py`：

```python
from sighttalk_api.ai.adapters import AsrAdapter, MultimodalAdapter, TtsAdapter
from sighttalk_api.ai.bailian_adapters import (
    BailianAsrAdapter,
    BailianMultimodalAdapter,
    BailianTtsAdapter,
)
from sighttalk_api.ai.mock_adapters import MockAsrAdapter, MockMultimodalAdapter, MockTtsAdapter
from sighttalk_api.core.config import Settings


def build_adapters(settings: Settings) -> tuple[AsrAdapter, MultimodalAdapter, TtsAdapter]:
    if settings.ai_provider == "mock":
        return MockAsrAdapter(), MockMultimodalAdapter(), MockTtsAdapter()
    if settings.ai_provider == "bailian":
        return (
            BailianAsrAdapter(settings),
            BailianMultimodalAdapter(settings),
            BailianTtsAdapter(settings),
        )
    raise ValueError(
        "Unsupported AI provider. Set VISION_ASSISTANT_AI_PROVIDER to 'mock' or 'bailian'."
    )
```

验证命令：

```bash
cd backend
uv run pytest tests/test_provider_config.py tests/test_bailian_adapters.py -v
uv run ruff check src/sighttalk_api/ai/provider_adapters.py tests/test_provider_config.py
uv run mypy
```

提交：

```bash
git add backend/src/sighttalk_api/ai/provider_adapters.py backend/tests/test_provider_config.py
git commit -m "feat(ai): 启用百炼 provider 工厂"
```

## Task 7: Document environment variables and Docker Compose wiring

目标：让本地和容器启动都能显式配置百炼 provider，且密钥只通过环境变量传入。

修改 `backend/.env.example`，追加：

```dotenv
VISION_ASSISTANT_AI_PROVIDER=mock
VISION_ASSISTANT_BAILIAN_API_KEY=
VISION_ASSISTANT_BAILIAN_COMPATIBLE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VISION_ASSISTANT_BAILIAN_ASR_MODEL=qwen3-asr-flash
VISION_ASSISTANT_BAILIAN_VISION_MODEL=qwen3.5-plus
VISION_ASSISTANT_BAILIAN_TTS_ENDPOINT=https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer
VISION_ASSISTANT_BAILIAN_TTS_MODEL=cosyvoice-v3-flash
VISION_ASSISTANT_BAILIAN_TTS_VOICE=longanyang
VISION_ASSISTANT_BAILIAN_TTS_FORMAT=wav
VISION_ASSISTANT_BAILIAN_TTS_SAMPLE_RATE=24000
VISION_ASSISTANT_BAILIAN_TIMEOUT_SECONDS=30
```

修改 `compose.yaml` 的 `api.environment`：

```yaml
      VISION_ASSISTANT_AI_PROVIDER: ${VISION_ASSISTANT_AI_PROVIDER:-mock}
      VISION_ASSISTANT_BAILIAN_API_KEY: ${VISION_ASSISTANT_BAILIAN_API_KEY:-}
      VISION_ASSISTANT_BAILIAN_COMPATIBLE_BASE_URL: ${VISION_ASSISTANT_BAILIAN_COMPATIBLE_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}
      VISION_ASSISTANT_BAILIAN_ASR_MODEL: ${VISION_ASSISTANT_BAILIAN_ASR_MODEL:-qwen3-asr-flash}
      VISION_ASSISTANT_BAILIAN_VISION_MODEL: ${VISION_ASSISTANT_BAILIAN_VISION_MODEL:-qwen3.5-plus}
      VISION_ASSISTANT_BAILIAN_TTS_ENDPOINT: ${VISION_ASSISTANT_BAILIAN_TTS_ENDPOINT:-https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer}
      VISION_ASSISTANT_BAILIAN_TTS_MODEL: ${VISION_ASSISTANT_BAILIAN_TTS_MODEL:-cosyvoice-v3-flash}
      VISION_ASSISTANT_BAILIAN_TTS_VOICE: ${VISION_ASSISTANT_BAILIAN_TTS_VOICE:-longanyang}
      VISION_ASSISTANT_BAILIAN_TTS_FORMAT: ${VISION_ASSISTANT_BAILIAN_TTS_FORMAT:-wav}
      VISION_ASSISTANT_BAILIAN_TTS_SAMPLE_RATE: ${VISION_ASSISTANT_BAILIAN_TTS_SAMPLE_RATE:-24000}
      VISION_ASSISTANT_BAILIAN_TIMEOUT_SECONDS: ${VISION_ASSISTANT_BAILIAN_TIMEOUT_SECONDS:-30}
```

修改 `README.md`，在“演示说明”和“容器启动”之间新增“百炼 provider 配置”：

````markdown
## 百炼 provider 配置

默认使用 mock provider：

```bash
export VISION_ASSISTANT_AI_PROVIDER=mock
```

使用阿里云百炼 provider：

```bash
export VISION_ASSISTANT_AI_PROVIDER=bailian
export VISION_ASSISTANT_BAILIAN_API_KEY="<your-bailian-api-key>"
```

可选模型配置：

```bash
export VISION_ASSISTANT_BAILIAN_ASR_MODEL=qwen3-asr-flash
export VISION_ASSISTANT_BAILIAN_VISION_MODEL=qwen3.5-plus
export VISION_ASSISTANT_BAILIAN_TTS_MODEL=cosyvoice-v3-flash
export VISION_ASSISTANT_BAILIAN_TTS_VOICE=longanyang
```

不要把真实 API Key 写入仓库。容器启动时，`compose.yaml` 会从当前 shell 环境读取这些变量。
````

验证命令：

```bash
docker compose config
VISION_ASSISTANT_AI_PROVIDER=bailian VISION_ASSISTANT_BAILIAN_API_KEY=sk-test docker compose config
```

预期结果：

```text
name: sighttalk-ai
services:
  api:
    environment:
      VISION_ASSISTANT_AI_PROVIDER: mock
```

第二条命令输出中应包含：

```text
      VISION_ASSISTANT_AI_PROVIDER: bailian
      VISION_ASSISTANT_BAILIAN_API_KEY: sk-test
```

提交：

```bash
git add backend/.env.example compose.yaml README.md
git commit -m "docs(readme): 补充百炼 provider 配置"
```

## Task 8: Full verification and PR

目标：确认新增 provider 没有破坏现有后端、前端和容器配置。

运行后端质量检查：

```bash
cd backend
uv run ruff check .
uv run mypy
uv run pytest -v
```

预期结果：

```text
All checks passed!
Success: no issues found in 1 source file
```

`pytest -v` 应全部通过，包含新增测试：

```text
tests/test_bailian_config.py::test_bailian_defaults_are_available PASSED
tests/test_bailian_config.py::test_bailian_settings_can_be_constructed_explicitly PASSED
tests/test_bailian_adapters.py::test_bailian_asr_posts_audio_data_url PASSED
tests/test_bailian_adapters.py::test_bailian_multimodal_posts_text_history_and_images PASSED
tests/test_bailian_adapters.py::test_bailian_tts_decodes_inline_audio_data PASSED
tests/test_bailian_adapters.py::test_bailian_tts_downloads_audio_url PASSED
```

运行前端质量检查：

```bash
cd frontend
npm run lint
npm run test:run
npm run build
```

预期结果：

```text
✓ built in
```

运行容器配置检查：

```bash
docker compose config
VISION_ASSISTANT_AI_PROVIDER=bailian VISION_ASSISTANT_BAILIAN_API_KEY=sk-test docker compose config
```

预期结果：两条命令均成功退出，且第二条输出包含 `VISION_ASSISTANT_AI_PROVIDER: bailian`。

最终提交检查：

```bash
git status --short
git log --oneline --max-count=8
```

预期结果：

```text
```

`git status --short` 无输出，`git log` 顶部包含本计划中的多个 Conventional Commits。

推送并创建单独 PR：

```bash
git push -u origin codex/bailian-provider-integration
gh pr create \
  --draft \
  --base main \
  --head codex/bailian-provider-integration \
  --title "[codex] 接入阿里云百炼 provider" \
  --body-file /tmp/bailian-provider-pr.md
```

PR 描述必须包含：

```markdown
## Summary

- 新增阿里云百炼 provider，覆盖 ASR、视觉问答和 TTS
- 保留 mock provider 作为默认本地演示配置
- 补充百炼环境变量、Docker Compose 透传和 README 使用说明

## Implementation

- ASR/视觉问答使用百炼 OpenAI 兼容 Chat Completions HTTP API
- TTS 使用百炼 CosyVoice 非实时 HTTP API
- 使用 `httpx.AsyncClient`，不引入 OpenAI SDK

## Tests

- `cd backend && uv run ruff check .`
- `cd backend && uv run mypy`
- `cd backend && uv run pytest -v`
- `cd frontend && npm run lint`
- `cd frontend && npm run test:run`
- `cd frontend && npm run build`
- `docker compose config`
- `VISION_ASSISTANT_AI_PROVIDER=bailian VISION_ASSISTANT_BAILIAN_API_KEY=sk-test docker compose config`

## Configuration

- 真实运行需要设置 `VISION_ASSISTANT_AI_PROVIDER=bailian`
- 真实运行需要设置 `VISION_ASSISTANT_BAILIAN_API_KEY`
- 本 PR 不包含真实 API Key
```

## Plan Self-Review

- 测试先行：每个实现任务都先写失败测试，再实现代码。
- 类型边界：新增 provider 只返回现有 `AsrResult`、`MultimodalResult`、`TtsResult`，不改 orchestration 合约。
- 密钥安全：配置只使用环境变量和 `.env.example` 空值，不写入真实密钥。
- Provider 隔离：百炼 HTTP 细节只存在于 `bailian_adapters.py`。
- Docker 可运行：Compose 默认仍是 mock；设置环境变量后才启用百炼。
- PR 粒度：实现分支 `codex/bailian-provider-integration` 独立发起 PR，不与 Docker 脚本分支混合。
- 未覆盖的真实调用风险：单元测试使用 fake HTTP client，不消耗百炼额度；真实 API 联调需要用户提供 API Key 后手动执行端到端演示。
