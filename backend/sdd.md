# SightTalk AI Backend SDD

## 1. 目标与边界

后端负责为 PC Web 前端提供实时 AI 视觉语音对话能力的服务端部分。首版必须支持：

- FastAPI HTTP API：健康检查、LiveKit 会话创建、会话结束。
- LiveKit 自托管媒体层：浏览器发布麦克风和摄像头，后端 agent 订阅。
- Python LiveKit agent worker：桥接用户音视频和 AI provider。
- 阿里云百炼作为默认实时多模态 provider。
- Provider adapter 接口：后续可增加 OpenAI、Gemini 或其他 provider，不改变前端协议。
- 成本控制：后端 agent 负责视觉抽帧、压缩、限频和模式切换。

首版不做登录、多用户房间、长期记忆、计费后台、移动端适配、本地模型推理或生产级监控。

## 2. 技术栈与项目结构

使用 Python、FastAPI、uv、Ruff、MyPy、Pytest。推荐结构：

```text
backend/
  pyproject.toml
  uv.lock
  .env.example
  sdd.md
  src/sighttalk_api/
    __init__.py
    main.py
    core/config.py
    api/v1/health.py
    api/v1/livekit.py
    schemas/livekit.py
    services/livekit_tokens.py
    services/session_registry.py
    agent/worker.py
    agent/media_policy.py
    providers/base.py
    providers/bailian.py
    providers/factory.py
  tests/
    test_health.py
    test_livekit_session.py
    test_provider_factory.py
    test_media_policy.py
```

命令必须符合仓库约定：

```bash
cd backend
uv sync --dev
uv run uvicorn sighttalk_api.main:app --reload
uv run ruff check .
uv run mypy
uv run pytest
```

## 3. 运行时架构

```text
React PC Web
  | POST /api/v1/livekit/session
  v
FastAPI Backend
  | creates room token
  v
LiveKit Server
  ^                              |
  | browser audio/video          | agent subscribes/publishes
  |                              v
Python LiveKit Agent Worker -> AIProvider -> Bailian Realtime API
```

FastAPI API 进程和 LiveKit agent worker 可以共享同一 Python package，但运行入口应分开：

- API：`uvicorn sighttalk_api.main:app`
- Agent worker：例如 `python -m sighttalk_api.agent.worker`

Agent worker 必须使用 LiveKit server credentials 连接自托管 LiveKit，监听或加入需要 AI assistant 的房间，订阅用户 audio/video tracks，并发布 assistant audio track 与 data messages。

## 4. 配置

创建 `backend/.env.example`，不得提交真实密钥。必须支持：

```dotenv
APP_ENV=development
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5173

LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
LIVEKIT_ROOM_TTL_SECONDS=3600

AI_PROVIDER=bailian
BAILIAN_API_KEY=
BAILIAN_REGION=
BAILIAN_WORKSPACE_ID=
BAILIAN_MODEL=
BAILIAN_REALTIME_URL=

DEFAULT_MEDIA_MODE=balanced
ECONOMY_MAX_VIDEO_FPS=0.2
BALANCED_MAX_VIDEO_FPS=1.0
ACCURATE_MAX_VIDEO_FPS=2.0
MAX_JPEG_EDGE=1024
JPEG_QUALITY=75
```

配置加载要求：

- 启动时校验 LiveKit 必填项。
- 当 `AI_PROVIDER=bailian` 时校验百炼必填项。
- 未设置 `AI_PROVIDER` 时默认 `bailian`。
- 不支持的 provider 必须产生明确配置错误。

## 5. HTTP API 契约

所有 API 前缀为 `/api/v1`。错误响应统一使用：

```json
{
  "error": {
    "code": "CONFIGURATION_ERROR",
    "message": "Human readable message",
    "request_id": "optional-request-id"
  }
}
```

### 5.1 GET /api/v1/health

响应：

```json
{
  "status": "ok",
  "service": "sighttalk-api"
}
```

### 5.2 POST /api/v1/livekit/session

请求：

```json
{
  "display_name": "optional user display name",
  "media_mode": "balanced"
}
```

字段规则：

- `display_name` 可选；为空时后端生成匿名名称。
- `media_mode` 可选，枚举 `economy`、`balanced`、`accurate`，默认 `balanced`。

成功响应：

```json
{
  "room_name": "sighttalk-01h...",
  "participant_identity": "user-01h...",
  "participant_token": "livekit-jwt",
  "livekit_url": "ws://localhost:7880",
  "expires_at": "2026-06-13T12:00:00Z",
  "assistant_identity": "assistant-sighttalk-01h...",
  "media_policy": {
    "mode": "balanced",
    "max_video_fps": 1.0,
    "max_jpeg_edge": 1024,
    "jpeg_quality": 75,
    "vad_enabled": true
  }
}
```

行为要求：

- 创建或确保 LiveKit room 可用。
- 生成只允许该 participant 加入该 room 的 token。
- token 过期时间与 `LIVEKIT_ROOM_TTL_SECONDS` 对齐。
- 不向前端返回百炼 API key、workspace、model endpoint 或 provider 内部 token。

### 5.3 POST /api/v1/livekit/session/{room_name}/end

请求：

```json
{
  "participant_identity": "user-01h..."
}
```

成功响应：

```json
{
  "status": "ended",
  "room_name": "sighttalk-01h..."
}
```

行为要求：

- 尝试断开 participant 和 assistant。
- 释放 session registry 中的状态。
- 如果 room 已不存在，返回幂等成功。

## 6. LiveKit Data Message 契约

后端 agent 和前端使用 LiveKit data messages 通信。JSON 必须包含 `type`、`session_id`、`timestamp`。

### 6.1 Topic

- 后端发给前端：`sighttalk.agent`
- 前端发给后端：`sighttalk.control`

### 6.2 后端事件

`agent.status`：

```json
{
  "type": "agent.status",
  "session_id": "sighttalk-01h...",
  "timestamp": "2026-06-13T12:00:00Z",
  "status": "listening"
}
```

`status` 枚举：`connecting`、`listening`、`thinking`、`speaking`、`error`、`ended`。

`transcript.delta`：

```json
{
  "type": "transcript.delta",
  "session_id": "sighttalk-01h...",
  "timestamp": "2026-06-13T12:00:01Z",
  "speaker": "assistant",
  "text": "你好",
  "message_id": "msg-01h..."
}
```

`speaker` 枚举：`user`、`assistant`。

`transcript.done`：

```json
{
  "type": "transcript.done",
  "session_id": "sighttalk-01h...",
  "timestamp": "2026-06-13T12:00:03Z",
  "speaker": "assistant",
  "text": "你好，我可以看到你的摄像头画面并听你说话。",
  "message_id": "msg-01h..."
}
```

`response.done`：

```json
{
  "type": "response.done",
  "session_id": "sighttalk-01h...",
  "timestamp": "2026-06-13T12:00:04Z",
  "message_id": "msg-01h...",
  "audio_playback_complete": false
}
```

`cost.estimate`：

```json
{
  "type": "cost.estimate",
  "session_id": "sighttalk-01h...",
  "timestamp": "2026-06-13T12:00:05Z",
  "audio_seconds": 12.4,
  "image_frames_sent": 3,
  "mode": "balanced"
}
```

`error`：

```json
{
  "type": "error",
  "session_id": "sighttalk-01h...",
  "timestamp": "2026-06-13T12:00:05Z",
  "code": "PROVIDER_UNAVAILABLE",
  "message": "AI provider is unavailable"
}
```

### 6.3 前端控制事件

`client.mode.update`：

```json
{
  "type": "client.mode.update",
  "session_id": "sighttalk-01h...",
  "timestamp": "2026-06-13T12:00:05Z",
  "mode": "accurate"
}
```

`client.interrupt`：

```json
{
  "type": "client.interrupt",
  "session_id": "sighttalk-01h...",
  "timestamp": "2026-06-13T12:00:06Z"
}
```

后端必须忽略未知事件类型，并为 malformed JSON 发布 `error` 事件或记录警告。

## 7. Provider Adapter

定义 `AIProvider` 抽象，Bailian 实现必须隐藏 vendor-specific 细节。

推荐接口语义：

```python
class AIProvider(Protocol):
    async def connect(self, session: ProviderSessionConfig) -> None: ...
    async def send_audio(self, chunk: AudioChunk) -> None: ...
    async def send_image(self, frame: ImageFrame) -> None: ...
    async def send_control(self, event: ControlEvent) -> None: ...
    async def events(self) -> AsyncIterator[ProviderEvent]: ...
    async def close(self) -> None: ...
```

`ProviderEvent` 至少覆盖：

- 用户语音转录增量与完成。
- AI 文本增量与完成。
- AI 音频输出 chunk 或可发布音频帧。
- provider 状态变化。
- provider 错误。

`BailianRealtimeProvider` 要求：

- 使用 `BAILIAN_API_KEY`、`BAILIAN_REGION`、`BAILIAN_WORKSPACE_ID`、`BAILIAN_MODEL`、`BAILIAN_REALTIME_URL`。
- 通过 WebSocket 接入百炼实时能力。
- 将内部错误映射为应用级 error code：`PROVIDER_CONFIGURATION_ERROR`、`PROVIDER_UNAVAILABLE`、`PROVIDER_PROTOCOL_ERROR`、`PROVIDER_RATE_LIMITED`。

## 8. Agent 媒体策略

Agent worker 必须实现：

- 订阅用户 audio track 和 video track。
- VAD 或 provider turn detection 可用时启用；不可用时仍要保证音频流可用。
- 按 `media_policy.mode` 抽样视频帧，并在发送 provider 前转 JPEG。
- JPEG 最大边默认 1024，质量默认 75。
- 统计 `audio_seconds` 和 `image_frames_sent`，定期发布 `cost.estimate`。
- 收到 `client.mode.update` 后更新后续抽样策略。
- 收到 `client.interrupt` 后通知 provider 中断当前回复，并发布 `agent.status=listening`。

模式行为：

| mode | 视觉策略 | 适用场景 |
| --- | --- | --- |
| `economy` | 仅显式视觉问题或极低频上下文帧 | 成本敏感 |
| `balanced` | 默认；交互中最多约 1 FPS | 常规体验 |
| `accurate` | 更高质量和频率，仍需限流 | 读文字、识别细节 |

## 9. Compose 与本地集成

后续实现需要在根目录 `compose.yaml` 中编排：

- `livekit`
- `backend`
- `agent`
- `frontend`

本地启动目标：

```bash
docker compose up --build
```

前端默认访问 backend：`http://localhost:8000`。LiveKit 默认：`ws://localhost:7880`。

## 10. 测试与验收

必须添加并通过：

```bash
cd backend
uv run ruff check .
uv run mypy
uv run pytest
```

测试场景：

- health endpoint 返回 ok。
- 缺少 LiveKit 配置时 session 创建返回结构化错误。
- 有效配置下 session 创建返回 token、room、identity、policy。
- session end 幂等。
- `AI_PROVIDER=bailian` 选择 `BailianRealtimeProvider`。
- 未知 provider 返回明确配置错误。
- media policy 对 `economy`、`balanced`、`accurate` 产生不同 fps/质量限制。
- provider mock 事件能被 agent 转换为 LiveKit data message。

集成验收：

- 前端能获取 session 并加入 LiveKit。
- Agent 能看到用户音视频 track。
- Agent 能发布 `agent.status`、`transcript.*`、`response.done`、`error`。
- 停止会话后 provider 和 LiveKit 资源释放。
