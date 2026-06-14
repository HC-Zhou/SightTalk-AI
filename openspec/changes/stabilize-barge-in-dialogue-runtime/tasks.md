## 1. Backend Stability Semantics

- [x] 1.1 Add response epoch state to the agent lifecycle or a dedicated dialogue stability coordinator.
- [x] 1.2 Stamp provider events with response epoch and optional provider response id at the Tooling/Lifecycle boundary.
- [x] 1.3 Drop stale `audio_delta`, assistant transcript, and `response_done` events when their epoch no longer matches the active response.
- [x] 1.4 Make explicit client interrupts and local VAD barge-in idempotent for the current playback epoch.
- [x] 1.5 Classify provider cancel failures and recoverable protocol errors as diagnostic-only instead of user-visible frontend errors.
- [x] 1.6 Add diagnostic event helpers with severity, surface, diagnostic id, session id, response epoch, code, and frontend-safe message fields.
- [x] 1.7 Keep terminal provider/runtime failures distinct from recoverable diagnostics and ensure terminal failures stop the affected runtime resources once.

## 2. Playback Coordination

- [x] 2.1 Centralize backend assistant playback state so audio queue clearing, playout completion, and stale audio rejection share one ordering model.
- [x] 2.2 Ensure interrupt clears queued assistant audio for the interrupted epoch before accepting new response audio.
- [x] 2.3 Ensure late audio from interrupted responses never reaches the LiveKit assistant audio source.
- [x] 2.4 Preserve normal response completion behavior for the current epoch after queued audio finishes playout.

## 3. Frontend Active Conversation Behavior

- [x] 3.1 Update realtime event handling so diagnostic and recoverable errors during active calls do not set visible `error` state.
- [x] 3.2 Treat legacy realtime `error` events during active calls as diagnostics unless explicitly marked terminal.
- [x] 3.3 Remove red user-visible interrupted styling from normal barge-in and return the visible state to listening-capable behavior.
- [x] 3.4 Add or refactor frontend playback coordination so interrupt stops old assistant audio locally without repeated multi-element pause/play churn.
- [x] 3.5 Preserve visible blocking errors for auth, media permission, configuration, or session-start failures before an active conversation begins.

## 4. Tests

- [x] 4.1 Add backend tests for rapid repeated interrupts producing one effective cancellation for the current epoch.
- [x] 4.2 Add backend tests for stale audio, transcript, and response completion events being ignored after epoch advance.
- [x] 4.3 Add backend tests for recoverable provider cancel/protocol errors emitting diagnostics without terminal session state.
- [x] 4.4 Add backend tests for terminal provider failures stopping runtime resources exactly once.
- [x] 4.5 Add frontend tests proving active-call diagnostic errors do not render an alert or red error state.
- [x] 4.6 Add frontend tests proving interrupt during assistant speech stops old audio and keeps the visible state neutral/listening-capable.

## 5. Validation

- [x] 5.1 Run backend lint, typing, and test commands from `backend/`.
- [x] 5.2 Run frontend lint, Vitest, and build commands from `frontend/`.
- [ ] 5.3 Manually verify a mock-provider session with repeated interrupt clicks does not show active-call error UI.
- [x] 5.4 Document any remaining provider-specific behavior differences in the change notes or design follow-up.
