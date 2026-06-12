# SightTalk API

Python 3.14 后端模板，使用 uv 管理依赖和命令。

## 开发

```bash
uv sync --dev
uv run uvicorn sighttalk_api.main:app --reload
```

## 常用命令

```bash
uv run ruff check .
uv run mypy
uv run pytest
```

## 环境变量

复制 `.env.example` 为 `.env` 后按环境调整。
