## Context

SightTalk already has a realtime E/T/C/L agent structure: Execution owns LiveKit media I/O, Tooling owns provider protocol, Context owns transcript and usage state, and Lifecycle coordinates state transitions. The current active conversation path still treats provider `error` events and interrupt status updates as frontend-visible state. During barge-in, the frontend pauses and mutes assistant audio locally while the backend clears the LiveKit audio source and sends provider `response.cancel`. Provider adapters can still emit late audio/transcript/response events or recoverable protocol errors after the interrupt, which can make playback fragmented and can move the UI into a red `error` state.

The stability goal is not to hide failures from operators. Failures must remain visible in logs, metrics, tests, and API/realtime diagnostics. The active user conversation surface, however, should stay calm: interruption is normal conversational behavior, and recoverable provider noise should not become a visual frontend error.

## Goals / Non-Goals

**Goals:**

- Make user barge-in idempotent, low-latency, and safe under rapid repeated interrupts.
- Prevent stale assistant audio, transcript, and response completion events from interrupted turns from affecting playback or UI state.
- Separate diagnostic errors from user-visible session state.
- Keep recoverable provider cancel/protocol errors in logs, metrics, and diagnostic events without showing red frontend feedback during active conversations.
- Centralize assistant playback ordering so queue clearing, playout completion, late audio dropping, and interrupt handling use one model.
- Preserve existing LiveKit topics and avoid breaking the primary frontend session API.

**Non-Goals:**

- Do not redesign authentication, conversation history, memory storage, or provider selection.
- Do not introduce a new media transport or replace LiveKit.
- Do not hide startup/auth/media-permission failures that prevent a session from starting.
- Do not build an operator dashboard; this change only emits structured diagnostics and metrics that a dashboard can later consume.

## Decisions

### Response Generation Epoch

Introduce a monotonic response generation, also called an epoch, owned by Lifecycle or a dedicated dialogue coordinator. Each assistant response starts under the current epoch. Interrupting increments the epoch and invalidates all pending events from earlier epochs.

Provider events that do not carry a provider-native response id should be stamped with the current epoch when they enter the Tooling/Lifecycle boundary. Events with a known provider response id should be mapped to the epoch active when that response began. Lifecycle must drop or diagnostic-log stale `audio_delta`, `transcript_delta`, `transcript_done`, and `response_done` events.

Rationale: clearing a local audio queue is not enough if the provider or network can still deliver old audio chunks. Epoch gating gives both backend and frontend a deterministic rule for stale event rejection.

Alternative considered: rely only on provider `response.cancel`. This is insufficient because cancel acknowledgement and late data ordering vary across providers.

### Diagnostic Error Taxonomy

Replace active-conversation use of generic frontend `error` state with explicit severity and surface semantics:

- `diagnostic.error`: recoverable or operator-facing error. Logged and emitted for tests/diagnostics. Does not alter visible frontend state.
- `session.degraded`: current turn failed or provider cancel had recoverable noise, but the session can continue listening.
- `session.terminal`: the session cannot continue. The runtime stops gracefully and records diagnostics; the active frontend view does not display a red error banner.

Existing `type: "error"` payloads from provider adapters should be classified at the Tooling/Lifecycle boundary. Only true terminal runtime failures may stop the session. Recoverable provider cancel failures, late cancel responses, malformed stale provider events, and provider protocol errors known to occur during interruption become diagnostics.

Rationale: users should not see operational noise during conversation. Operators still need the details for debugging and alerting.

Alternative considered: keep `error` events and suppress only in the frontend. This would reduce visible errors but preserve an ambiguous contract and make tests less precise.

### Interrupt State Is Internal

Keep `interrupted` as an internal lifecycle transition if useful for metrics, but do not present it as a red frontend status during normal barge-in. After the local interrupt action, the user-facing state should immediately return to `listening` or stay in a neutral active state.

Rationale: barge-in is a successful control action, not a failure. A visible red interrupted state trains users to think the system broke.

Alternative considered: show a transient "interrupted" badge. This adds visual noise and does not help the conversation recover.

### Playback Coordinator

Introduce a single playback coordination boundary for assistant audio. It owns:

- the current playback epoch,
- ordered audio queue writes,
- queue clear on interrupt,
- playout completion,
- late audio dropping,
- browser audio element attach/pause/play behavior on the frontend.

Backend Execution should continue to own the LiveKit audio source, but Lifecycle should not scatter playback state across unrelated branches. Frontend playback should avoid repeatedly pausing and resuming multiple audio elements as a side effect of transcript events.

Rationale: fragmented audio usually comes from multiple actors mutating the same playback state. A single coordinator makes the ordering testable.

Alternative considered: keep the current element-level pause/resume behavior and add retries. Retries do not solve stale audio acceptance or inconsistent playout completion.

### Backward-Compatible Realtime Contract

Keep the existing LiveKit topics (`sighttalk.agent`, `sighttalk.control`). Add optional metadata fields such as `response_epoch`, `response_id`, `diagnostic_id`, `severity`, and `surface` to relevant events. Frontend handlers should tolerate both old and new payloads during migration.

Rationale: this avoids forcing a transport migration while tightening semantics.

Alternative considered: create a new topic for diagnostics only. That can be added later, but a single topic with explicit `surface` is sufficient for this stabilization pass.

## Risks / Trade-offs

- [Risk] Provider adapters expose inconsistent response ids. -> Mitigation: assign epochs at the Tooling/Lifecycle boundary and treat provider ids as optional correlation metadata.
- [Risk] Suppressing user-visible errors could mask real failures. -> Mitigation: terminal errors still stop the runtime and all errors emit structured diagnostics, metrics, and logs.
- [Risk] Dropping stale transcripts may remove partial text from interrupted assistant replies. -> Mitigation: interrupted assistant output should not be treated as finalized conversation history unless it was completed before the epoch changed.
- [Risk] Frontend and backend may temporarily disagree on current epoch during migration. -> Mitigation: backend remains authoritative; frontend epoch filtering is a second defensive layer.
- [Risk] Tests may need broad fixture updates because current tests expect visible errors. -> Mitigation: update active-conversation tests separately from startup/auth error tests.

## Migration Plan

1. Add backend diagnostic event helpers and error classification without changing frontend behavior.
2. Add response epoch tracking to Lifecycle/Tooling and include epoch metadata in realtime events.
3. Drop stale backend audio/transcript/response events after interrupts.
4. Refactor assistant playback into a backend coordination boundary and update existing LiveKit audio source interactions.
5. Update frontend realtime event handling so active-session diagnostics do not set visible `error` state.
6. Add or refactor frontend playback coordination to avoid multiple pause/play paths.
7. Update tests for rapid interrupts, provider cancel failures, stale event dropping, and no visible active-session error feedback.

Rollback: keep the existing event payload shapes valid and feature-flag the new stability handling if needed. If regressions appear, disable epoch filtering and diagnostic classification while preserving the existing session start/end behavior.

## Open Questions

- Should `session.terminal` during an active call silently end the call or show a neutral "ended" state after media cleanup?
- Should diagnostic events be published to the frontend at all in production, or only logged server-side?
- What minimum interrupt debounce window feels best: no debounce, one per animation frame, or a short server-side coalescing window such as 150-250 ms?

## Implementation Notes

- Bailian and OpenAI realtime adapters both use provider cancel commands that can race with provider-side response lifecycle events. This implementation treats cancel/protocol noise during active conversation as recoverable diagnostics and relies on response epoch gating to drop late assistant output.
- Gemini Live exposes different response and terminal event shapes, including go-away style payloads. Terminal provider signals remain terminal diagnostics, while ordinary protocol errors during active conversation are recoverable unless explicitly classified as terminal.
- Provider response ids are optional correlation data. The backend response epoch is authoritative for stale event rejection because provider ids are not consistent across adapters.
- The in-app Browser tool was not available in this session. Repeated interrupt/no-visible-error behavior is covered by automated backend lifecycle and frontend Vitest tests; a full manual browser run should be performed when browser automation or a local QA browser is available.
