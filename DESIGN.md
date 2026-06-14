# SightTalk AI 设计文档

## 1. 项目概述

SightTalk AI 是一个面向 PC Web 的视觉语音助手。浏览器采集麦克风和摄像头媒体流，将它们发布到 LiveKit 房间；后端以 assistant participant 的身份加入同一个房间，订阅用户音视频，归一化处理后转发给配置的 AI provider，并把状态、转录文本和助手音频事件实时推回浏览器。

当前实现目标是一个可用的端到端实时多模态对话系统，包含 FastAPI、React、LiveKit 和可插拔的 provider 层。默认生产 provider 是阿里云百炼；同时支持 OpenAI Realtime 和 Gemini Live 适配器，便于在不同模型能力、成本和可用性之间切换。

## 2. 运行时 Pipeline

```text
浏览器
  -> 登录认证 API
  -> 创建 LiveKit session
  -> 发布麦克风/摄像头 tracks
  -> 启动后端 assistant

后端 API
  -> 创建 LiveKit room/token
  -> 启动一个 room 级别的 agent task

后端 Agent
  -> 订阅用户音频/视频
  -> 应用降噪、VAD、媒体策略
  -> 将音频和抽样 JPEG 画面发送给 provider
  -> 接收 provider 的转录、音频和状态事件
  -> 发布标准化 LiveKit data/audio 事件

前端
  -> 播放 assistant 音频
  -> 维护 session 状态
  -> 视频结束后通过鉴权 API 保存最终文字转录
  -> 在主页侧边栏展示已保存的对话记录
```

## 3. 用户故事

### 3.1 计划实现的用户故事

| 编号 | 计划用户故事 | 验收目标 |
| --- | --- | --- |
| US-01 | 作为用户，我可以先注册并登录，再使用助手。 | 应用保存 bearer token，能恢复当前用户，并保护 session API。 |
| US-02 | 作为用户，我可以从主页开始一次视频语音对话。 | 浏览器请求摄像头/麦克风权限，加入 LiveKit，并发布本地 tracks。 |
| US-03 | 作为用户，我可以自然说话，助手会持续监听。 | 后端 agent 订阅音频，转发给 provider，并接收 provider 的实时事件。 |
| US-04 | 作为用户，我可以让助手结合摄像头画面回答问题。 | 后端按媒体策略抽取画面、压缩图片，并发送给 provider。 |
| US-05 | 作为用户，我可以听到助手语音回复，并看到会话状态。 | assistant 发布音频 track，并向前端发送标准化状态事件。 |
| US-06 | 作为用户，我可以在助手说话时打断它。 | 前端发送 `client.interrupt`；后端清空待播放音频并向 provider 发送取消指令。 |
| US-07 | 作为用户，我可以结束视频会话并释放本地设备。 | 前端断开 LiveKit，停止本地媒体 tracks，并调用后端 end API。 |
| US-08 | 作为用户，我可以回看已结束视频对话的文字记录。 | 视频结束后保存 transcript，在主页侧边栏展示，点击后打开详情。 |
| US-09 | 作为用户，视频进行中画面应该保持干净。 | 视频激活时隐藏历史侧边栏，结束后恢复显示。 |
| US-11 | 作为运营/开发者，我可以切换不同 AI provider，获得真实实时多模态回复。 | 通过 `AI_PROVIDER` 选择 `bailian`、`openai` 或 `gemini`，并使用对应 provider 凭据。 |
| US-12 | 作为运营/开发者，我可以在效果和成本之间调节媒体策略。 | 通过环境变量和媒体模式控制抽帧频率、JPEG 尺寸和质量。 |

### 3.2 最终实现情况

| 编号 | 状态 | 实现说明 |
| --- | --- | --- |
| US-01 | 已实现 | 认证接口位于 `/api/v1/auth`；前端将 token 保存为 `sighttalk.auth.token`。 |
| US-02 | 已实现 | `useSightTalkSession` 请求本地媒体、创建后端 LiveKit session、加入房间并发布 tracks。 |
| US-03 | 已实现 | `LiveKitExecution` 消费 16 kHz 单声道 PCM；`AgentLifecycle` 将音频转交给 `AgentTooling`。 |
| US-04 | 已实现 | 后端按频率抽取视频帧，缩放并 JPEG 压缩，且只在用户音频开始后发送图像。 |
| US-05 | 已实现 | assistant 音频作为 LiveKit audio track 发布；状态和转录事件通过 `sighttalk.agent` 发送。 |
| US-06 | 已实现 | 手动打断和本地 VAD 插话会优先清空本地播放队列、恢复用户输入，并向 provider 发送 cancel。 |
| US-07 | 已实现 | 停止会话会释放本地 tracks，并调用 `/api/v1/livekit/session/{room}/end`。 |
| US-08 | 已实现，服务端保存 | 完成后的 transcript 通过 `/api/v1/conversations` 保存到后端；接口使用 bearer token 鉴权，并按用户隔离。 |
| US-09 | 已实现 | 视频激活期间隐藏历史侧边栏和文字详情；结束后恢复。 |
| US-11 | 已实现 | Provider factory 支持 `bailian`、`openai`、`gemini`；默认配置仍是 `bailian`。 |
| US-12 | 已实现 | `economy`、`balanced`、`accurate` 三种模式控制视频帧率；JPEG 边长和质量可配置。 |

### 3.3 延后实现的用户故事

| 用户故事 | 延后原因 |
| --- | --- |
| 对话历史分页和搜索 | 当前历史 API 返回最近 50 条，尚未提供分页、搜索和删除能力。 |
| 多实例 session registry | 当前 `SessionRegistry` 和 `LiveKitAgentManager` 是进程内状态；生产环境需要 Redis/数据库协调。 |
| 运营计费看板 | 当前已有用量估算事件，但尚未实现计费 UI、告警、配额或按用户报表。 |

## 4. 运营成本控制策略

实时多模态助手的成本主要来自音频输入、视觉帧、上下文长度和生成音频。设计时因此从开发、媒体、上下文、provider 和运营控制多个层面考虑成本。

### 4.1 设计时想到的成本控制技巧

| 技巧 | 目标 |
| --- | --- |
| 媒体模式 | 允许运营方按场景选择更低或更高的视觉采样成本。 |
| 后端抽帧 | 不直接发送原始视频，只按配置 FPS 发送受控 JPEG 帧。 |
| JPEG 缩放和质量压缩 | 降低图像 payload 大小、网络成本和 provider 视觉输入成本。 |
| 音频优先的视觉门控 | 用户还没开始说话时不发送摄像头帧，避免空闲视觉成本。 |
| 助手说话时暂停输入 | 避免助手回复期间继续把环境音/画面送入 provider，降低重复处理。 |
| 本地 VAD 和插话检测 | 本地检测 speech start 和 barge-in，减少无效助手播放与后续生成浪费。 |
| 降噪 | 减少噪声音频转发和误触发语音检测。 |
| 短期上下文限制 | 控制长会话中的 prompt/context 增长。 |
| 记忆检索数量和阈值 | 只取少量相关记忆，避免把过多历史塞进上下文。 |
| 记忆摘要 | 当短期上下文过长时压缩旧轮次。 |
| Provider 抽象 | 在不改前端协议的情况下切换到更便宜、更稳定或特定能力更合适的 provider。 |
| 显式配额和预算 | 对每个用户或 session 的音频秒数、图像帧数、provider 调用设置硬限制。 |
| 服务端文本历史 | 只保存文字，不保存视频，降低存储和合规压力。 |

### 4.2 实际采用的成本控制技巧

| 技巧 | 是否采用 | 实现说明 |
| --- | --- | --- |
| 媒体模式 | 已采用 | `economy`、`balanced`、`accurate` 策略通过后端配置和前端控制消息生效。 |
| 后端抽帧 | 已采用 | `LiveKitExecution._consume_video` 根据 `max_video_fps` 限制发送帧数。默认 economy `0.2`、balanced `0.5`、accurate `1.0` FPS。 |
| JPEG 缩放和压缩 | 已采用 | `encode_video_frame` 按 `MAX_JPEG_EDGE` 缩略；`encode_jpeg_under_limit` 降低质量和尺寸以满足字节预算。 |
| 音频优先的视觉门控 | 已采用 | `AgentLifecycle.handle_image_frame` 等待 provider ready 和用户音频开始后才转发图像。 |
| 助手说话时暂停输入 | 已采用 | `_begin_assistant_playback` 清除 `_input_enabled`；播放结束或打断后恢复输入。 |
| 本地 VAD 插话 | 已采用 | `LocalVAD` 可在 assistant 播放期间触发 `local_vad_barge_in`。 |
| 降噪 | 已采用 | `NoiseSuppressor` 由 `AUDIO_NOISE_SUPPRESSION_ENABLED` 控制。 |
| 用量估算事件 | 已采用 | `cost.estimate` 向前端报告音频秒数、已发送图像帧数和媒体模式。 |
| 短期上下文限制 | 已采用 | `SHORT_MEMORY_MAX_MESSAGES` 和 `SHORT_MEMORY_MAX_ESTIMATED_TOKENS` 控制上下文规模。 |
| 记忆检索限制 | 已采用 | `MEMORY_SEARCH_LIMIT` 和 `MEMORY_SEARCH_THRESHOLD` 控制记忆检索范围。 |
| 记忆摘要 hook | 已采用 | `ContextWorker.summarize_if_needed` 和 `MemoryWorker.add_short_term_summary` 在后端支持时可使用。 |
| Provider 抽象 | 已采用 | `AIProvider` 协议和 `create_provider` 支持 `bailian`、`openai`、`gemini` 多 provider 切换。 |
| 硬配额/预算 | 未采用 | 当前只估算用量，不会因配额自动拒绝或停止 session。 |
| 服务端 transcript 历史 | 已采用 | `/api/v1/conversations` 只保存文字 transcript，并通过当前登录用户鉴权隔离。 |

## 5. 设计取舍

### 5.1 服务端对话历史

已实现的历史侧边栏通过带鉴权的后端 API 保存和读取完成后的对话文字。后端当前使用文件存储，按用户 id 隔离并限制每个用户最多保留 50 条；这样比浏览器本地存储更接近生产语义，也便于后续迁移到数据库、增加分页、搜索和删除。

### 5.2 进程内编排

当前 agent manager 将 room agent task 保存在内存中。这样本地开发简单，也不需要额外队列依赖。生产多实例部署前，应把 active session 状态迁移到 Redis 或数据库协调层。

### 5.3 打断语义

当前打断优先优化体感响应速度：前端立刻暂停音频，后端清空播放队列，恢复用户输入，并向 provider 发送 cancel。这样用户可以尽快重新开始表达，不需要等待助手当前语音播放完成。

## 6. 建议的下一步

1. 完善多 provider 的配置校验、连通性检查和错误提示。
2. 增加每个 session 的音频秒数和图像帧数上限。
3. 水平扩展前，将进程内 session/agent registry 替换为 Redis 或其他共享状态层。
