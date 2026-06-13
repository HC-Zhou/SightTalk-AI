FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN uv sync --dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "sighttalk_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
