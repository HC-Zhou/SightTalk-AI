## Why

SightTalk's realtime video conversation can become unstable when the user speaks over the assistant: provider cancel races, late audio chunks, and recoverable protocol errors can surface as visible frontend errors or fragmented assistant playback. This change stabilizes barge-in behavior by treating conversational interruptions as normal runtime events and by separating diagnostics from user-visible session state.

## What Changes

- Introduce a dialogue stability runtime contract for active video conversations.
- Add response generation/epoch semantics so audio, transcript, and response completion events from interrupted assistant turns can be ignored after they become stale.
- Split realtime errors into recoverable diagnostics, degraded session signals, and terminal session failures.
- Ensure provider cancel failures and recoverable provider protocol errors are logged and emitted as diagnostics, but do not drive red frontend error UI during an active conversation.
- Keep the user-facing conversation surface calm during interruptions: no red error banner, no visible error status, and no red interrupted state during normal barge-in.
- Centralize assistant playback coordination so interrupt, queue clearing, audio playout, and late audio dropping have one ordering model.
- Add tests for rapid barge-in, late provider events, recoverable cancel errors, terminal errors, and frontend non-visual error handling.

## Capabilities

### New Capabilities

- `dialogue-stability-runtime`: Stable realtime conversation semantics for barge-in, playback coordination, stale event rejection, diagnostic-only errors, and terminal failure handling.

### Modified Capabilities

- None.

## Impact

- Affected backend code: agent lifecycle, provider tooling/event mapping, realtime metrics, assistant audio playback coordination, and provider adapters where recoverable cancel/protocol errors are classified.
- Affected frontend code: session realtime event handling, active-conversation status mapping, interrupt handling, assistant playback coordination, and tests.
- Affected realtime contract: adds diagnostic/degraded/terminal event semantics and response generation metadata while preserving existing LiveKit topics.
- Affected tests: backend lifecycle/tooling tests and frontend Vitest coverage for interruption and error visibility behavior.
