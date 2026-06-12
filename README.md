# SightTalk AI

企业级全栈模板工程，分为 Python 后端和 React 前端。

## 技术栈

- `backend/`: Python 3.14, uv, FastAPI, Pydantic Settings, Ruff, MyPy, Pytest
- `frontend/`: React, TypeScript, Vite, npm, ESLint, Prettier, Vitest
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

## 容器启动

```bash
docker compose up --build
```
