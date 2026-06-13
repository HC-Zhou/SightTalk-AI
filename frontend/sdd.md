# SightTalk AI Frontend SDD

## 1. 目标与边界

前端负责 PC Web 端 AI 视觉语音对话体验。首版必须支持：

- 请求摄像头和麦克风权限。
- 展示本地摄像头预览。
- 调用后端创建 LiveKit session。
- 使用 `livekit-client` 加入 LiveKit room 并发布本地 audio/video tracks。
- 接收 assistant 音频、状态、转录、错误和成本估算事件。
- 提供开始、停止、麦克风开关、摄像头开关、打断、成本模式切换。

首版只适配桌面浏览器，不做移动端布局、登录、多用户房间、长期历史记录或 provider 配置 UI。

## 2. 技术栈与项目结构

使用 React、TypeScript、Vite、ESLint、Prettier、Vitest、Testing Library、`livekit-client`。推荐结构：

```text
frontend/
  package.json
  package-lock.json
  vite.config.ts
  index.html
  sdd.md
  src/
    main.tsx
    app/App.tsx
    app/App.test.tsx
    features/session/api.ts
    features/session/types.ts
    features/session/useSightTalkSession.ts
    features/session/livekitEvents.ts
    features/media/useLocalMedia.ts
    shared/config.ts
    shared/components/
```

命令必须符合仓库约定：

```bash
cd frontend
npm install
npm run dev
npm run lint
npm run test:run
npm run build
```

## 3. 用户体验

首屏是可用应用，不做营销落地页。PC 布局建议：

```text
┌──────────────────────────────────────────────────────────┐
│ Top bar: SightTalk AI | backend/livekit/agent status      │
├──────────────────────────────┬───────────────────────────┤
│ Camera preview               │ Conversation              │
│                              │ - user transcript         │
│ local video                  │ - assistant transcript    │
│ assistant speaking indicator │ - cost estimate           │
├──────────────────────────────┴───────────────────────────┤
│ Controls: Start Stop Mic Camera Interrupt Mode            │
└──────────────────────────────────────────────────────────┘
```

状态：

- `idle`：未开始，显示开始按钮。
- `requesting-permission`：正在请求摄像头/麦克风。
- `connecting`：已拿到媒体，正在创建 session 和加入 LiveKit。
- `listening`：AI 正在听。
- `thinking`：AI 正在处理。
- `speaking`：AI 正在回复。
- `error`：可恢复错误，允许重试。
- `ended`：已停止。

权限失败时必须显示明确恢复提示，不得进入 LiveKit room。

## 4. 环境配置

创建 `frontend/.env.example`：

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

前端不得包含百炼 API key、LiveKit API secret 或任何 server-side credential。

## 5. Backend API 契约

### 5.1 POST /api/v1/livekit/session

请求类型：

```ts
export type MediaMode = 'economy' | 'balanced' | 'accurate';

export interface CreateLiveKitSessionRequest {
  display_name?: string;
  media_mode?: MediaMode;
}
```

响应类型：

```ts
export interface MediaPolicy {
  mode: MediaMode;
  max_video_fps: number;
  max_jpeg_edge: number;
  jpeg_quality: number;
  vad_enabled: boolean;
}

export interface CreateLiveKitSessionResponse {
  room_name: string;
  participant_identity: string;
  participant_token: string;
  livekit_url: string;
  expires_at: string;
  assistant_identity: string;
  media_policy: MediaPolicy;
}
```

前端行为：

- 默认请求 `media_mode: 'balanced'`。
- 成功后使用 `livekit_url` 和 `participant_token` 加入 room。
- 不缓存 token 到 localStorage。
- 请求失败时显示错误并停留在可重试状态。

### 5.2 POST /api/v1/livekit/session/{room_name}/end

请求类型：

```ts
export interface EndLiveKitSessionRequest {
  participant_identity: string;
}
```

响应类型：

```ts
export interface EndLiveKitSessionResponse {
  status: 'ended';
  room_name: string;
}
```

前端停止会话时：

- 先断开 LiveKit room。
- 再尽力调用 end API。
- 即使 end API 失败，也要释放本地 camera/microphone tracks 并回到 ended/idle 可恢复状态。

### 5.3 错误响应

```ts
export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    request_id?: string;
  };
}
```

UI 显示 `message`，开发日志可包含 `code` 和 `request_id`。

## 6. LiveKit Client 行为

使用 `livekit-client`：

- 创建 `Room`。
- 使用后端返回 token 加入。
- 发布 microphone audio track。
- 发布 camera video track。
- 渲染本地 video preview。
- 订阅 assistant audio track 并自动播放。
- 监听 connection state 和 participant/track 事件。
- 发送和接收 data messages。

浏览器媒体约束：

```ts
const mediaConstraints = {
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  },
  video: {
    width: { ideal: 1280 },
    height: { ideal: 720 },
    frameRate: { ideal: 30, max: 30 },
  },
};
```

前端发布完整 camera track，由后端 agent 决定抽帧和压缩。前端不直接把图片发给百炼。

## 7. LiveKit Data Message 契约

### 7.1 Topic

- 接收后端事件：`sighttalk.agent`
- 发送前端控制：`sighttalk.control`

所有 payload 都是 UTF-8 JSON，并包含：

```ts
interface BaseRealtimeEvent {
  type: string;
  session_id: string;
  timestamp: string;
}
```

### 7.2 接收事件

```ts
export type AgentStatus =
  | 'connecting'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'error'
  | 'ended';

export interface AgentStatusEvent extends BaseRealtimeEvent {
  type: 'agent.status';
  status: AgentStatus;
}
```

```ts
export interface TranscriptDeltaEvent extends BaseRealtimeEvent {
  type: 'transcript.delta';
  speaker: 'user' | 'assistant';
  text: string;
  message_id: string;
}

export interface TranscriptDoneEvent extends BaseRealtimeEvent {
  type: 'transcript.done';
  speaker: 'user' | 'assistant';
  text: string;
  message_id: string;
}
```

```ts
export interface ResponseDoneEvent extends BaseRealtimeEvent {
  type: 'response.done';
  message_id: string;
  audio_playback_complete: boolean;
}
```

```ts
export interface CostEstimateEvent extends BaseRealtimeEvent {
  type: 'cost.estimate';
  audio_seconds: number;
  image_frames_sent: number;
  mode: MediaMode;
}
```

```ts
export interface AgentErrorEvent extends BaseRealtimeEvent {
  type: 'error';
  code: string;
  message: string;
}
```

前端必须：

- 将 `agent.status` 映射到 UI 状态。
- 用 `transcript.delta` 更新正在生成的消息。
- 用 `transcript.done` 固化消息。
- 显示 `cost.estimate` 的音频秒数、图片帧数和模式。
- 对未知事件类型忽略并记录 debug log。

### 7.3 发送控制事件

切换模式：

```ts
export interface ClientModeUpdateEvent extends BaseRealtimeEvent {
  type: 'client.mode.update';
  mode: MediaMode;
}
```

打断：

```ts
export interface ClientInterruptEvent extends BaseRealtimeEvent {
  type: 'client.interrupt';
}
```

前端发送控制事件后应乐观更新本地控件状态，但以后端后续 `agent.status` 和 `cost.estimate` 作为最终状态。

## 8. 组件与状态设计

建议实现一个主 hook：`useSightTalkSession`。它负责：

- 本地 media permission。
- session API 调用。
- LiveKit room 生命周期。
- data message 编解码。
- transcript 状态。
- assistant status。
- cost estimate。
- error 状态。

核心状态类型：

```ts
interface SightTalkState {
  status: 'idle' | 'requesting-permission' | 'connecting' | AgentStatus;
  mediaMode: MediaMode;
  localPreviewStream?: MediaStream;
  roomName?: string;
  participantIdentity?: string;
  assistantIdentity?: string;
  messages: ConversationMessage[];
  cost?: {
    audioSeconds: number;
    imageFramesSent: number;
    mode: MediaMode;
  };
  error?: {
    code: string;
    message: string;
  };
}
```

控件要求：

- Start：从 idle/ended/error 状态开始新会话。
- Stop：断开 room、停止本地 tracks、调用 end API。
- Mic：mute/unmute local audio track。
- Camera：mute/unmute local video track，并同步预览状态。
- Interrupt：发送 `client.interrupt`。
- Mode segmented control：`economy`、`balanced`、`accurate`。

## 9. 错误处理

必须区分：

- 权限错误：摄像头或麦克风被拒绝。
- API 错误：后端 session 创建或结束失败。
- LiveKit 连接错误：token、网络、room disconnected。
- Agent/provider 错误：后端通过 data message 发送。

恢复策略：

- 权限错误允许用户重新点击 Start。
- API/LiveKit/agent 错误显示 message，释放本地资源，允许重试。
- Stop 操作必须尽力完成，不能因为 end API 失败而卡住 UI。

## 10. 测试与验收

必须添加并通过：

```bash
cd frontend
npm run lint
npm run test:run
npm run build
```

测试场景：

- idle 状态显示 Start，未显示 transcript。
- Start 时请求 media permission，并调用 session API。
- 权限被拒绝时显示 recoverable error，不调用 LiveKit connect。
- session API 成功后使用 token 加入 LiveKit 并发布 audio/video。
- 收到 `agent.status` 后 UI 状态更新。
- 收到 `transcript.delta` 和 `transcript.done` 后消息正确展示和固化。
- 模式切换发送 `client.mode.update`。
- Interrupt 发送 `client.interrupt`。
- Stop 释放 local tracks、断开 room、调用 end API。
- 未知 data message 不崩溃。

集成验收：

- `docker compose up --build` 后可打开 PC 浏览器页面。
- 用户授权摄像头和麦克风后看到本地预览。
- 页面能连接 LiveKit room。
- 页面能收到后端 agent 的状态、转录、错误或成本事件。
- 用户停止会话后摄像头灯熄灭，页面回到可再次开始状态。
