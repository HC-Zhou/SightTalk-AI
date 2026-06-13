# SightTalk API

Python FastAPI backend and realtime agent package for SightTalk AI.

## Development

```bash
uv sync --dev
uv run uvicorn sighttalk_api.main:app --reload
uv run ruff check .
uv run mypy
uv run pytest
```

Copy `.env.example` to `.env` for local configuration. Do not commit secrets.
