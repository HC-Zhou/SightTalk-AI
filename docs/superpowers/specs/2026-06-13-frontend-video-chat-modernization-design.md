# Frontend Video Chat Modernization Design

## Goal

将现有 React 前端从“信息面板式 Demo”升级为 PC Web 端的视频对话体验：沿用当前后端 WebSocket 事件流，优化接口地址配置、连接封装、错误处理，并把页面做成豆包视频聊天风格的横屏界面。

验收标准：

- 前端不再在 `App.tsx` 中硬编码 `http://127.0.0.1:8000`、`ws://127.0.0.1:8000` 和音频资源拼接逻辑。
- WebSocket 客户端封装能统一构建会话地址、识别连接状态、处理 JSON 解析失败和关闭原因。
- 页面第一屏就是可用的视频对话界面，不做营销页或说明页。
- PC 横屏下主画面占据视觉中心，底部悬浮圆形控制区，右侧保留实时字幕和历史字幕轨。
- 实时字幕层接入现有事件：助手侧使用 `assistant.text.delta` 流式更新，用户侧使用 `transcript.final` 最终文本更新。
- 媒体权限、WebSocket 断开、服务端 `error` 事件能在页面中以清晰但不打断布局的方式呈现。
- 现有后端事件协议不改变，不新增百炼配置入口，不把 provider/API key 暴露给前端。

## Approved Visual Direction

用户已确认采用“豆包视频聊天风格，但适配 PC Web 横屏”的版本。

视觉原则：

- 以视频画面作为主体，不再使用黑色空面板；默认状态应呈现暖色、真实摄像头占位或本地摄像头预览。
- 底部控制区采用豆包式大圆按钮：麦克风、上传/共享、摄像头或画面采集、挂断。
- 当前字幕以半透明浮层贴近画面底部中心，适合通话时快速扫读。
- PC 横屏增加右侧字幕轨，用于承载更长的实时字幕、历史轮次、连接状态和错误提示。
- 色彩应克制、清晰，避免整页单一深色或黑块感；主画面可以是暖灰/浅金调，控制层保持半透明。

## Scope

本次只修改前端请求封装和页面体验：

- `frontend/src/shared/` 中新增或重构 API 配置、WebSocket 客户端、事件类型处理。
- `frontend/src/app` 或现有 `App.tsx` 拆分视频通话 UI 组件。
- `frontend/src/App.css` 重做布局、响应式和状态样式。
- 补充前端单元测试。

明确不做：

- 不改后端 WebSocket 路径、事件类型或数据字段。
- 不接入 WebRTC、低延迟双向音频流或新的实时 ASR 协议。
- 不在前端暴露阿里云百炼 provider、模型、API key 或后端环境配置。
- 不引入重型 UI 框架。

## Backend Contract

当前后端 WebSocket 路径为：

```text
/ws/session/{session_id}
```

前端继续发送：

```text
session.start
audio.chunk
video.frame
utterance.end
session.stop
```

前端继续接收：

```text
session.ready
policy.update
transcript.final
assistant.thinking
assistant.text.delta
assistant.text.done
tts.ready
cost.snapshot
error
```

`tts.ready.audio_url` 是相对路径时，前端按 API HTTP origin 解析为完整音频 URL。

## API And WebSocket Design

新增 `frontend/src/shared/apiConfig.ts`：

- 读取 `import.meta.env.VITE_API_ORIGIN` 作为 HTTP API origin。
- 未配置时默认 `http://127.0.0.1:8000`，保持本地开发可直接运行。
- 支持从 HTTP origin 派生 WebSocket origin：`http` 转 `ws`，`https` 转 `wss`。
- 提供 `buildSessionWebSocketUrl(sessionId)`。
- 提供 `resolveApiAssetUrl(pathOrUrl)`，用于解析 `tts.ready.audio_url`。
- 对 session id 做 `encodeURIComponent`，避免路径注入或特殊字符破坏 URL。

重构 `frontend/src/shared/wsClient.ts`：

- 构造参数从裸 `url` 调整为 `sessionId` 和可选 API 配置，内部调用地址构建函数。
- 保留 `onEvent`、`onStatusChange` 回调，新增可选 `onClientError` 回调。
- `connect()` 只负责建立连接并在打开后发送 `session.start`。
- `send()` 返回 `boolean`，连接未打开时返回 `false`，避免音频/视频采集阶段无限排队。
- `close()` 在连接仍打开时先发送 `session.stop`，再关闭 socket。
- `message` 事件使用安全 JSON 解析。解析失败时触发客户端错误状态，并提供清晰错误信息。
- WebSocket `close` 时记录 code/reason；非正常关闭显示为可恢复连接错误。

## Subtitle State Design

在 `sessionReducer` 中扩展字幕状态，或新增轻量 selector：

```ts
type LiveSubtitle = {
  speaker: "user" | "assistant";
  text: string;
  phase: "listening" | "thinking" | "streaming" | "final";
};
```

事件映射：

- `assistant.thinking`：显示助手正在思考的状态。
- `assistant.text.delta`：追加助手草稿，同时更新 `liveSubtitle` 为 `streaming`。
- `assistant.text.done`：把助手消息写入历史，`liveSubtitle` 进入 `final`。
- `transcript.final`：把用户消息写入历史，并显示用户最终字幕。
- `error`：不写入对话历史，但显示到字幕轨的状态区域。

当前后端没有用户侧 interim ASR 事件，所以用户说话时只能显示“正在聆听/处理中”，无法逐字滚动。用户最终文本在 `transcript.final` 到达后出现；助手回复可以通过 `assistant.text.delta` 实时更新。

## UI Layout Design

组件拆分：

- `VideoCallApp`：顶层会话编排，持有连接、采集、播放状态。
- `VideoStage`：主视频画面、本地预览、中心字幕和顶部状态叠层。
- `CallControls`：底部圆形控制按钮，包含麦克风、上传/共享、画面采集、挂断。
- `LiveSubtitleOverlay`：主画面上的当前字幕。
- `SubtitleRail`：PC 右侧实时字幕轨和历史字幕。
- `ConnectionBadge`：连接状态、成本快照、错误状态的紧凑显示。

桌面横屏布局：

```text
┌───────────────────────────────────────────┬──────────────────────┐
│ Top status overlay                         │ Subtitle rail         │
│                                           │ Live / History / Cost  │
│              Video stage                  │ Errors                │
│                                           │                      │
│        Live subtitle overlay              │                      │
│                                           │                      │
│      Mic  Share  Camera  Hangup           │                      │
└───────────────────────────────────────────┴──────────────────────┘
```

响应式：

- `>= 1100px`：主画面 + 右侧字幕轨双栏。
- `768px - 1099px`：字幕轨收敛为底部/侧边浮层，主画面保持优先。
- `< 768px`：纵向栈布局，保留底部控制按钮，但尺寸收紧。

## Error Handling

错误来源和呈现：

- 摄像头/麦克风权限错误：顶部状态条显示明确原因，控制按钮进入不可用或可重试状态。
- WebSocket 建连失败：状态显示“连接失败”，保留重连按钮。
- 服务端 `error` 事件：显示 `stage`、`message`，`retryable` 为真时允许重试当前连接。
- JSON 解析失败：作为前端客户端错误处理，不让页面崩溃。
- 音频播放失败：字幕轨显示“语音播放失败”，不影响文字对话继续展示。

## Test Plan

前端需要新增或更新测试：

- `apiConfig`：HTTP origin 默认值、环境变量覆盖、WS origin 派生、音频 URL 解析。
- `wsClient`：连接打开后发送 `session.start`、未连接时 `send()` 返回 `false`、非法 JSON 触发客户端错误。
- `sessionReducer`：`assistant.text.delta` 更新实时字幕，`assistant.text.done` 归档助手消息，`transcript.final` 显示用户最终字幕。
- `App` 或拆分组件：连接状态、错误提示、字幕轨和主要控制按钮可见。

最终验证命令：

```bash
cd frontend
npm run lint
npm run test:run
npm run build
```

视觉验证：

- 启动前端开发服务器。
- 使用浏览器检查桌面横屏视口，确认主画面不是黑屏空块，底部控制区和右侧字幕轨清晰可见。
- 检查窄屏视口，确认字幕和按钮不重叠。

## Self Review

- 规格只依赖当前后端已存在事件，不要求后端同步改协议。
- API 地址配置把 Docker、本地开发、部署环境的差异集中到一个模块。
- 字幕方案明确区分助手侧流式字幕和用户侧最终字幕，避免承诺后端当前不支持的实时 ASR 效果。
- 页面设计优先满足 PC 横屏视频通话，不再保留面板式 Demo 的视觉结构。
- 实现拆分足够小，可以按 API 配置、连接封装、字幕状态、页面组件、视觉验证分步提交和开 PR。
