# SightTalk AI

AI 视觉对话助手 Web MVP，分为 Python 后端和 React 前端。用户授权摄像头和麦克风后，前端通过 WebSocket 上传音频片段和低频抽样画面，后端使用可替换的 AI 适配器完成转写、视觉问答、TTS 和成本统计。

## 技术栈

- `backend/`: Python 3.14, uv, FastAPI, Pydantic Settings, Ruff, MyPy, Pytest
- `frontend/`: React, TypeScript, Vite, npm, ESLint, Vitest
- `.github/workflows/ci.yml`: 后端和前端基础 CI
- `compose.yaml`: 本地容器化启动模板

## 目录结构

```text
.
├── backend
│   ├── src/sighttalk_api
│   └── tests
├── frontend
│   ├── src
│   └── public
└── compose.yaml
```

## 本地开发

后端：

```bash
cd backend
uv sync --dev
uv run uvicorn sighttalk_api.main:app --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/v1/health
```

预期响应：

```json
{"status":"ok"}
```

前端：

```bash
cd frontend
npm install
npm run dev
```

默认地址：

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:8000/api/v1/health>
- OpenAPI: <http://localhost:8000/docs>

## 质量检查

```bash
cd backend
uv run ruff check .
uv run mypy
uv run pytest

cd ../frontend
npm run lint
npm run test:run
npm run build
```

## 演示说明

第一版默认使用 mock AI 适配器，方便本地稳定演示并避免产生模型调用成本。完整演示流程见后续 `docs/demo-script.md`。

## Demo Flow

1. 启动后端服务，确认 `/api/v1/health` 返回 `{"status":"ok"}`。
2. 启动前端服务并打开 <http://127.0.0.1:5173>。
3. 点击 `开始`。
4. 允许浏览器访问摄像头和麦克风。
5. 等待摄像头预览出现。
6. 说一句简短问题。
7. 点击 `我说完了`。
8. 确认页面出现用户转写、助手回答、TTS 播放尝试和成本面板更新。

默认应用使用 deterministic mock AI 适配器。这样本地演示稳定且不会产生付费模型调用；真实 provider 的配置入口会在后续适配器中保留。

## 容器启动

```bash
docker compose up --build
```
