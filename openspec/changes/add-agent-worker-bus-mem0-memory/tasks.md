## 1. Phase 1: Contracts, Settings, and Safe Scaffolding

- [x] 1.1 Add backend settings for `MEMORY_BACKEND`, Mem0 connection/configuration fields, Mem0 search controls, and short-term context thresholds.
- [x] 1.2 Extend the provider protocol with `ProviderCapabilities`, `capabilities()`, `update_context(context)`, and `create_response()` without changing existing provider behavior.
- [x] 1.3 Add typed frame, frame processor, processor pipeline, worker, worker bus, worker registry, and runner scaffolding behind the current lifecycle path.
- [x] 1.4 Add `SessionState`, `ShortTermContext`, `ContextBuilder`, and `ContextSummarizer` scaffolding while preserving the existing `AgentSessionContext` facade.
- [x] 1.5 Add `LongTermMemory`, local JSONL-compatible memory adapter, disabled memory adapter, and Mem0 adapter/fake-client path without requiring external Mem0 in CI.
- [x] 1.6 Add unit tests for frame priority/cancellation, bus routing, worker activation, short-term context aggregation/summarization fallback, Mem0 filters/add metadata, and provider capability defaults.
- [x] 1.7 Run `cd backend && uv run ruff check . && uv run mypy && uv run pytest`.

## 2. Phase 2: ContextWorker and MemoryWorker Migration

- [x] 2.1 Add `ContextWorker` to own short-term context updates, prompt construction, and summary state.
- [x] 2.2 Add `MemoryWorker` to own long-term search/add operations and non-fatal memory failure handling.
- [x] 2.3 Move current JSONL prompt hydration and response-done memory flushing behind workers while `AgentLifecycle` still drives execution.
- [x] 2.4 Add integration tests for authenticated user isolation, memory failure fallback, and prompt injection guard.

## 3. Phase 3: WorkerRunner Runtime Assembly

- [x] 3.1 Add `TransportWorker`, `ProviderWorker`, and `MainAgentWorker` wrappers for the existing Execution, Tooling, and Lifecycle responsibilities.
- [x] 3.2 Convert `LiveKitRoomAgent` into runner assembly while preserving public LiveKit topics and event payload fields.
- [x] 3.3 Add runner tests for startup/shutdown ordering, terminal error convergence, and interrupt cancellation semantics.

## 4. Phase 4: Manual Provider Response Gate

- [x] 4.1 Implement manual response mode for mock provider and Bailian adapter behind provider capabilities.
- [x] 4.2 Set Bailian `turn_detection.create_response=false` only when manual response is enabled.
- [x] 4.3 Implement per-turn flow from user transcript completion to memory search, context update, and explicit provider response creation.
- [x] 4.4 Add provider-order tests for `transcript_done -> memory search -> context update -> create_response`.

## 5. Phase 5: Future Worker Extension Points

- [x] 5.1 Add job and handoff frame APIs for specialist workers.
- [x] 5.2 Add extension tests for target worker routing and timed job completion/failure.
- [x] 5.3 Document follow-up worker types for visual experts, task experts, and analytics sidecars.
