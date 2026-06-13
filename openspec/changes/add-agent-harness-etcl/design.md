## Context

SightTalk currently has a FastAPI backend, React/Vite frontend, LiveKit media transport, and a provider abstraction for Bailian or mock realtime AI. The realtime backend path is functional but tightly coupled: `LiveKitRoomAgent` handles LiveKit room lifecycle, media consumption, assistant audio playback, provider readiness gates, provider event pumping, and error recovery, while `AgentSession` owns provider calls, frontend event mapping, cost counters, and control messages.

This change separates the first four harness pillars from the Agent Harness Engineering ETCLOVG model:

- Execution: runtime environment and media I/O.
- Tooling: model/provider tool protocol and normalized events.
- Context: session state, transcripts, cost counters, and memory.
- Lifecycle: orchestration, readiness, task ownership, and state/error transitions.

The same change introduces local authentication so memories can be stored by a stable `user_id` instead of anonymous room identities.

## Goals / Non-Goals

**Goals:**

- Introduce local JSON-backed user authentication with PBKDF2-SHA256 password storage and JWT Bearer authorization.
- Protect LiveKit session lifecycle endpoints without changing their request body contracts.
- Refactor the realtime agent into independently testable E/T/C/L harness modules.
- Preserve existing LiveKit data topics and frontend realtime event payloads.
- Persist user-scoped text memories and inject recent memories into provider system prompts.
- Add frontend login, registration, token persistence, authenticated API calls, and logout.
- Keep validation covered by backend unit tests and frontend Vitest tests.

**Non-Goals:**

- Do not implement the remaining Observation, Verification, or Governance harness pillars beyond existing error events and tests.
- Do not add a database, external identity provider, OAuth, refresh tokens, or account recovery.
- Do not change LiveKit room token semantics, media payload shapes, or frontend realtime event names.
- Do not replace the `AIProvider` provider abstraction.

## Decisions

### Local JSON Auth Store

Use a small `UserStore` backed by `${SIGHTTALK_DATA_DIR}/users.json`, plus an `AuthService` for password hashing and JWT creation/validation. Passwords are stored as PBKDF2-SHA256 records with salt and iteration metadata. JWTs use `AUTH_SECRET_KEY` and `AUTH_TOKEN_TTL_SECONDS`.

Rationale: the repository is still a local/dev full-stack app and the plan explicitly avoids a database. Keeping storage behind a service makes later database migration straightforward.

Alternative considered: SQLite. It would improve concurrent write behavior but adds schema/migration work outside the current phase.

### FastAPI Auth Dependency

Add a reusable dependency that parses `Authorization: Bearer <token>`, validates the JWT, loads the user, and raises `401` for missing, invalid, expired, or unknown-user tokens. Apply it to LiveKit session creation, agent start, and session end. Keep request bodies unchanged. Store `user_id` in session registry records so agent start can pass the authenticated owner into the harness.

Rationale: protecting endpoints at the router boundary keeps downstream code focused on room/session behavior.

Alternative considered: frontend-only identity. That would not protect session APIs and would not provide trusted memory ownership.

### Harness Module Boundaries

Create harness modules under the backend agent package:

- `execution.py` owns LiveKit room connection, data publication, track subscription callbacks, media stream consumption, assistant audio track publishing/playback, frame encoding use, and cleanup.
- `tooling.py` owns provider connection, provider retries/errors, `send_audio`, `send_image`, interrupts, media mode updates, and provider event normalization into frontend payloads.
- `context.py` owns the session context object: user/session ids, current media policy, cost counters, transcript messages, memory loading, prompt construction, and memory flushing.
- `lifecycle.py` wires Execution, Tooling, and Context together. It owns state transitions, task creation/cancellation, provider-ready/audio-ready gates, terminal error convergence, and event publication order.

`LiveKitRoomAgent` remains a thin adapter that constructs these collaborators and delegates `run`/`stop`.

Rationale: this preserves current behavior while making each harness pillar unit-testable.

Alternative considered: a single generic `Harness` class. That would reduce file count but retain most coupling.

### Provider Compatibility

Keep `AIProvider`, `ProviderSessionConfig`, `AudioChunk`, `ImageFrame`, `ControlEvent`, and `ProviderEvent` as the provider-facing contract. Tooling normalizes provider events to existing LiveKit frontend payloads and enforces image sending only after user audio has reached the provider. Bailian-specific connection retry and protocol details remain isolated from lifecycle and execution code.

Rationale: provider swaps should not affect LiveKit room handling or lifecycle state tests.

Alternative considered: move all provider event mapping into each provider. That would duplicate frontend event shape logic across providers.

### Text Memory Model

Use `${SIGHTTALK_DATA_DIR}/memory/<user_id>.jsonl` as an append-only memory file. Each line stores a JSON object with timestamp, user id, session id, role/source, and text. The context layer loads the most recent `HARNESS_MEMORY_MAX_ITEMS` valid entries, ignores corrupt lines, and injects them into the provider system prompt. On `response.done` and session end, finalized transcript text is flushed to memory.

Rationale: JSONL keeps writes simple and tolerates partially corrupt files better than a single large JSON document.

Alternative considered: summarize memory before writing. That can reduce prompt size, but it introduces additional provider calls and belongs in a later memory quality pass.

### Frontend Auth State

Add an auth client and top-level auth state in the React app. If no valid local token exists, render a compact login/register view. On successful login/register, persist the token in `localStorage`. All session API calls include the token. Logout clears the token, stops any active session, and returns to the auth view.

Rationale: this keeps the first screen usable while meeting the new API authorization contract.

Alternative considered: route-based auth. The app currently has one primary interaction surface, so routing is unnecessary for this phase.

## Risks / Trade-offs

- Local JSON writes can race under multiple backend workers -> keep writes synchronous and scoped for local development; document that production should migrate to a database-backed store.
- JWT secret misconfiguration can invalidate all tokens -> provide `.env.example` defaults for local dev and require a non-default value for production deployment guidance.
- Prompt injection from stored user text could degrade provider behavior -> inject memories in a clearly delimited "User memory" section and keep the base system prompt authoritative.
- Memory files can grow over time -> limit reads with `HARNESS_MEMORY_MAX_ITEMS`; add later compaction outside this change.
- Refactor can regress realtime media behavior -> preserve data topics/payloads and cover readiness gates, event mapping, and terminal errors with tests.

## Migration Plan

1. Add auth and memory settings with local defaults.
2. Add auth services and API routes; add frontend auth client/UI.
3. Add memory store and context prompt/memory behavior.
4. Extract current runtime behavior into E/T/C/L harness modules while keeping `LiveKitRoomAgent` as adapter.
5. Protect LiveKit endpoints and pass `user_id` into session registry and agent startup.
6. Update Docker Compose to mount persistent backend data.
7. Run backend and frontend validation commands.

Rollback: remove auth dependencies from LiveKit routes and instantiate the previous `LiveKitRoomAgent`/`AgentSession` path if realtime regressions are found before release.

## Open Questions

- Should registration return an authenticated token immediately or require a separate login call? This design chooses immediate token issuance for a simpler first-run flow.
- Should memories include both user and assistant transcripts or only user-provided facts? This design stores finalized text from both roles and leaves summarization/filtering for a later phase.
