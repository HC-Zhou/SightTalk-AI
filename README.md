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

## 容器启动

```bash
docker compose up --build
```
