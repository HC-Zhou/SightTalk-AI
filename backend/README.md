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

## Long-Term Memory

The default memory backend is local JSONL:

```bash
MEMORY_BACKEND=local_jsonl
```

To use Mem0 Platform or a self-hosted Mem0 API from `docker compose`, set:

```bash
MEMORY_BACKEND=mem0
MEM0_API_KEY=<your mem0 api key>
# Optional for self-hosted Mem0 API:
MEM0_HOST=http://mem0.example.internal:3000
MEM0_AGENT_ID=sighttalk
MEM0_SEARCH_LIMIT=5
MEM0_SEARCH_THRESHOLD=0.3
```

For OSS/local SDK mode, provide a JSON config object instead of a hosted API:

```bash
MEMORY_BACKEND=mem0
MEM0_LOCAL_CONFIG_JSON='{"vector_store":{"provider":"qdrant","config":{"collection_name":"sighttalk_memories","embedding_model_dims":1024,"host":"qdrant","port":6333}}}'
```

`compose.yaml` forwards all `MEMORY_BACKEND`, `MEM0_*`, short-term memory, and
`AI_MANUAL_RESPONSE_ENABLED` variables into the backend container.

When using the Docker Compose Qdrant service, open the local vector dashboard at
`http://localhost:6333/dashboard`. This dashboard shows Qdrant collections and
vectors; it is not a Mem0 product dashboard.
