## Why

SightTalk already has a LiveKit/Bailian realtime harness, but memory hydration, transcript persistence, provider prompting, and runtime orchestration are still tightly coupled in the active lifecycle. The next step is to add a Pipecat-inspired internal architecture that can support per-turn memory retrieval, safe context compression, and future specialist workers without changing the public LiveKit session or data-message contracts.

## What Changes

- Add an internal typed frame and worker bus model for prioritized, cancellable in-process agent work.
- Split session context responsibilities into short-term conversation state, context building, summarization, and long-term memory access.
- Add a long-term memory protocol with local JSONL fallback and a Mem0 implementation path.
- Extend provider contracts with optional manual response capabilities so memory retrieval can happen before provider response creation.
- Keep public `sighttalk.agent`, `sighttalk.control`, LiveKit session APIs, and realtime payload fields compatible.
- Phase the migration so phase 1 adds interfaces, settings, fake/local memory behavior, and unit tests without changing the active runtime path.

## Capabilities

### New Capabilities

- `agent-worker-bus`: Typed frame, processor, worker, bus, registry, and runner contracts for internal agent orchestration.
- `short-term-context`: Session-local transcript aggregation, recent-window retention, context construction, and summarization fallback behavior.
- `long-term-mem0-memory`: Long-term memory search and turn persistence through a protocol with Mem0 and local JSONL-compatible implementations.

### Modified Capabilities

- None.

## Impact

- Backend agent runtime modules under `backend/src/sighttalk_api/agent/`.
- Backend provider protocol under `backend/src/sighttalk_api/providers/`.
- Backend memory service under `backend/src/sighttalk_api/services/`.
- Backend settings and `.env.example` memory configuration.
- Backend unit tests for frame priority, worker bus routing, short-term context, provider capabilities, and memory metadata/filtering.
- Optional future dependency on `mem0ai`; local and CI defaults continue to work without external Mem0.
