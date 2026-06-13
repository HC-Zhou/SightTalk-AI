## Context

SightTalk currently uses a LiveKit execution layer, provider tooling, session context, and lifecycle harness. This ETCL structure is already a good boundary, but short-term context, JSONL memory hydration, provider prompt construction, and response timing are still coupled to `AgentSessionContext` and `AgentTooling`. That makes it difficult to retrieve long-term memory per turn, compress the rolling transcript, and add specialist workers without expanding the lifecycle into a coordinator for every concern.

Pipecat provides useful reference patterns: frames move through processors, context aggregators build provider context, summarizers compress stale turns, and worker runners bridge independent workers over a bus. SightTalk will copy these architectural patterns, not the Pipecat runtime, because the public contract remains LiveKit data topics plus the Bailian realtime provider adapter.

## Goals / Non-Goals

**Goals:**

- Preserve public LiveKit session APIs, `sighttalk.agent`, `sighttalk.control`, and existing frontend event payload shapes.
- Introduce typed frames, frame processors, workers, an in-process worker bus, a worker registry, and a runner as internal extension points.
- Split short-term session memory into `SessionState`, `ShortTermContext`, and `ContextBuilder`.
- Add summarization thresholds and fallback behavior so provider prompts remain bounded.
- Add a long-term memory protocol with Mem0-compatible search/add semantics and local JSONL fallback for development and CI.
- Add provider capability flags and optional manual response hooks, enabling future per-turn memory retrieval before response creation.
- Phase adoption so initial interfaces and tests do not change the active runtime path.

**Non-Goals:**

- Replacing LiveKit, the current API surface, or the Bailian realtime adapter.
- Importing the Pipecat runtime or requiring Pipecat as a dependency.
- Making the bus distributed with Redis, NATS, or a cross-process runner.
- Migrating existing JSONL transcript memory into Mem0.
- Implementing specialist workers such as vision experts or analytics sidecars in this change.
- Blocking conversation flow when Mem0 is unavailable.

## Decisions

### Use an In-Process Typed Frame Bus

The first bus implementation is in-process and asyncio-based. Frames have a stable id, timestamp, priority, source, optional target, interruptibility flag, and payload. System frames have higher priority and are never dropped by interruption. Control and data frames can be cancelled when the runner interrupts a turn.

Alternative considered: move directly to Redis/NATS. That would add operational complexity before SightTalk has more than one process-local runtime, so it is deferred.

### Keep ETCL as the Runtime Shell During Phase 1 and 2

Phase 1 adds interfaces and tests behind the current lifecycle. Phase 2 moves memory and context building into `ContextWorker` and `MemoryWorker` while ETCL still drives startup. Phase 3 wraps transport, provider, context, memory, and main orchestration as workers behind `WorkerRunner`.

Alternative considered: replace `AgentLifecycle` immediately. That would risk regressions in LiveKit media sequencing, interrupt handling, and terminal error behavior.

### Model Short-Term Context Separately From Long-Term Memory

`ShortTermContext` stores finalized user/assistant turns, pending transcript deltas, media policy, usage counters, current summary, and recent-turn windows. `ContextBuilder` emits provider context with this ordering: base instruction, untrusted memory block, short-term summary, recent finalized turns, and safe pending provider/tool sequences.

Alternative considered: keep `AgentSessionContext.build_system_prompt` as the only prompt builder. That does not support per-turn retrieved memory or summarization without growing a single mutable class.

### Summarize Conservatively and Fall Back to Recent Window

Summarization triggers when finalized messages exceed `SHORT_MEMORY_MAX_MESSAGES=24` or estimated prompt tokens exceed `SHORT_MEMORY_MAX_ESTIMATED_TOKENS=8000`. Summaries preserve base instructions, memory blocks, the last four turns, and incomplete provider/tool sequences. If summarization fails, context construction uses a bounded recent window instead of blocking the session.

Alternative considered: prune old turns without summarization. That is simpler, but it loses stable user goals and references during longer sessions.

### Mem0 Is a Long-Term Memory Backend, Not an Instruction Source

The long-term memory protocol exposes `search(scope, query, limit, threshold)`, `add_turn(scope, messages, metadata)`, and `close()`. Mem0 writes use `messages` plus `user_id`, `agent_id`, and `run_id`; search filters use `user_id` and `agent_id` by default and do not filter by `run_id`, allowing cross-session recall. Retrieved memories are injected as untrusted user memory and are always lower priority than the base system instruction.

Alternative considered: keep JSONL as production semantic memory. JSONL remains useful for local fallback and transcript audit, but it cannot provide semantic search or conflict handling.

### Provider Manual Response Is Capability-Gated

Providers expose `ProviderCapabilities(supports_manual_response, supports_context_update)`. The future manual flow is `TranscriptDoneFrame(user)` to `MemorySearchJob` to `ProviderContextUpdateFrame` to `ProviderResponseCreateFrame`. Bailian will set `turn_detection.create_response=false` only when manual response mode is enabled, then the runtime explicitly calls `create_response()` after memory injection.

Alternative considered: always enable manual response. Mock/local providers and provider accounts that do not support the full vendor flow need to keep automatic behavior until the manual path is verified.

## Risks / Trade-offs

- Mem0 API or dependency changes -> isolate it behind `LongTermMemory` and keep local JSONL fallback as the default in development and CI.
- Prompt injection through remembered text -> label memory blocks as untrusted context and keep them below the base system instruction.
- Bus cancellation could drop important events -> classify system frames as non-interruptible and test interrupt cancellation semantics.
- Context summarization can be slow or fail -> use threshold-based triggering and recent-window fallback.
- Manual provider response can regress latency or event order -> keep it capability-gated and verify the exact `transcript_done -> memory search -> context update -> create_response` order before enabling by default.

## Migration Plan

1. Add settings, provider capabilities, memory protocol, local/Mem0 memory services, short-term context, context builder, summarizer shell, frame types, worker bus, registry, runner, and unit tests. Do not change active runtime flow.
2. Move current prompt construction and memory persistence behind `ContextWorker` and `MemoryWorker`, still driven by existing lifecycle.
3. Wrap LiveKit transport, provider, context, memory, and main coordination in workers; let `LiveKitRoomAgent` assemble and run a `WorkerRunner`.
4. Enable manual response gating for mock and Bailian providers after per-turn retrieval and context update tests pass.
5. Add job and handoff APIs for future specialist workers.

Rollback for each phase is to keep or restore the prior ETCL direct path, because public API and payload contracts are unchanged.

## Open Questions

- Whether production should use hosted Mem0 via API key, local Mem0 config, or a self-hosted endpoint first.
- Whether summarization should initially call the configured realtime/text provider or a separate cheaper text model.
- Whether long-term memory should store only extracted facts/preferences or also retain full transcript audit in a separate sink.

## Future Worker Extension Points

The runner exposes `job.request`, `job.result`, `job.error`, and `handoff.request` frame shapes for specialist workers. These frames are targeted by worker id and carry stable job or handoff ids so callers can correlate completion, timeout, or failure without coupling specialists to the main lifecycle.

Initial follow-up worker candidates:

- Visual expert worker: receives `vision.inspect` jobs with the latest visual context and returns structured observations for detailed scene questions.
- Task expert worker: receives `task.plan` or `task.execute` jobs for multi-step user tasks that should not block the realtime provider stream.
- Analytics sidecar worker: receives low-priority session telemetry frames for cost, latency, interruption, and media-policy analysis without affecting user-visible event order.
