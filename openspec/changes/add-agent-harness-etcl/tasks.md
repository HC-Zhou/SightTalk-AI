## 1. Backend Auth Foundation

- [x] 1.1 Add settings for `SIGHTTALK_DATA_DIR`, `AUTH_SECRET_KEY`, `AUTH_TOKEN_TTL_SECONDS`, and `HARNESS_MEMORY_MAX_ITEMS`.
- [x] 1.2 Implement local user models, JSON user store, PBKDF2-SHA256 password hashing, and password verification.
- [x] 1.3 Implement JWT token creation and validation with expiration handling.
- [x] 1.4 Add FastAPI auth schemas, `/api/v1/auth/register`, `/api/v1/auth/login`, and `/api/v1/auth/me`.
- [x] 1.5 Add reusable current-user dependency that returns `401` for missing, invalid, expired, or unknown-user Bearer tokens.
- [x] 1.6 Add backend auth tests for registration, duplicate registration, successful login, failed login, `/me`, token expiry, and absence of plaintext passwords.

## 2. Backend Memory Foundation

- [x] 2.1 Implement user-scoped JSONL memory store under `${SIGHTTALK_DATA_DIR}/memory/<user_id>.jsonl`.
- [x] 2.2 Implement recent-memory retrieval with `HARNESS_MEMORY_MAX_ITEMS` and malformed-line tolerance.
- [x] 2.3 Implement context prompt construction that preserves the base SightTalk prompt and injects a delimited memory section only when memories exist.
- [x] 2.4 Implement transcript tracking and idempotent memory flushing on `response.done` and session end.
- [x] 2.5 Add memory tests for user isolation, recent item limits, corrupt file tolerance, prompt injection, and empty transcript no-op behavior.

## 3. Harness E/T/C/L Refactor

- [x] 3.1 Add Context harness module for session identity, authenticated `user_id`, media policy, counters, transcripts, cost events, and memory integration.
- [x] 3.2 Add Tooling harness module for provider connect/close, audio/image/control calls, audio-before-image guard, provider event iteration, and frontend event normalization.
- [x] 3.3 Add Execution harness module for LiveKit room connection, callbacks, media stream consumption, assistant audio track playback, event publication, and cleanup.
- [x] 3.4 Add Lifecycle harness module for state transitions, provider-ready and audio-ready gates, task management, interrupt handling, terminal error convergence, and event sequencing.
- [x] 3.5 Convert `LiveKitRoomAgent` into a thin adapter that constructs E/T/C/L collaborators and delegates `run` and `stop`.
- [x] 3.6 Keep existing LiveKit data topics and realtime event payloads unchanged.
- [x] 3.7 Add harness tests for provider readiness gating, image-before-audio gating, provider event mapping, control mapping, counters, and single terminal error publication.

## 4. LiveKit API Integration

- [x] 4.1 Protect `POST /api/v1/livekit/session`, `POST /api/v1/livekit/session/{room_name}/agent/start`, and `POST /api/v1/livekit/session/{room_name}/end` with the current-user dependency.
- [x] 4.2 Extend session registry records to carry the authenticated `user_id`.
- [x] 4.3 Pass `user_id` from the session registry into `LiveKitAgentManager.start` and the room agent harness.
- [x] 4.4 Preserve existing LiveKit session request bodies and response payload contracts.
- [x] 4.5 Add session API tests for unauthenticated `401` responses and authenticated session creation/start/end behavior.

## 5. Frontend Auth Flow

- [x] 5.1 Add auth API client functions and types for register, login, and `/me`.
- [x] 5.2 Add top-level auth state that loads and verifies a stored token from `localStorage`.
- [x] 5.3 Add login/register UI for unauthenticated users.
- [x] 5.4 Attach `Authorization: Bearer <token>` to LiveKit session create, agent start, mock event, and end calls.
- [x] 5.5 Add logout behavior that stops any active session, clears `localStorage`, and returns to the auth UI.
- [x] 5.6 Add frontend tests for unauthenticated UI, successful auth, Bearer headers on session calls, and logout token cleanup.

## 6. Configuration and Validation

- [x] 6.1 Update `backend/.env.example` with auth, data directory, and memory settings.
- [x] 6.2 Update `compose.yaml` to set `SIGHTTALK_DATA_DIR=/app/data` and mount a persistent backend data volume.
- [x] 6.3 Run `cd backend && uv run ruff check .`.
- [x] 6.4 Run `cd backend && uv run mypy`.
- [x] 6.5 Run `cd backend && uv run pytest`.
- [x] 6.6 Run `cd frontend && npm run lint`.
- [x] 6.7 Run `cd frontend && npm run test:run`.
- [x] 6.8 Run `cd frontend && npm run build`.
