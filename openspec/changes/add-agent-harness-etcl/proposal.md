## Why

SightTalk's realtime agent flow is currently concentrated in `LiveKitRoomAgent` and `AgentSession`, which makes provider I/O, LiveKit media handling, session state, and error recovery difficult to test independently. The next architecture step is to introduce the Execution, Tooling, Context, and Lifecycle harness pillars while adding stable local user identity so cross-session memory can be attributed to a `user_id`.

## What Changes

- Add local account registration, login, and `/me` APIs using PBKDF2-SHA256 password hashes, JWT Bearer tokens, and JSON file persistence.
- Require Bearer authentication for LiveKit session creation, agent start, and session end while keeping request and realtime event payload shapes unchanged.
- Add persistent data configuration for users and memory, including `SIGHTTALK_DATA_DIR`, `AUTH_SECRET_KEY`, `AUTH_TOKEN_TTL_SECONDS`, and `HARNESS_MEMORY_MAX_ITEMS`.
- Refactor the realtime agent into E/T/C/L harness modules:
  - Execution owns LiveKit room connection, track subscription, media stream consumption, assistant audio output, event publication, and cleanup.
  - Tooling owns provider session calls, provider event normalization, Bailian audio-before-image behavior, retries, interrupt handling, and media mode updates.
  - Context owns session state, transcripts, cost counters, and user-scoped long-term memory.
  - Lifecycle owns state transitions, task startup/shutdown, readiness gates, terminal error handling, and event publication sequencing.
- Keep `LiveKitRoomAgent` as a thin adapter that wires LiveKit callbacks into the harness and preserves existing frontend data topics and event formats.
- Add frontend login/register UI, token persistence in `localStorage`, authenticated session API calls, and logout behavior.

## Capabilities

### New Capabilities

- `local-user-auth`: Local user registration, login, token validation, authenticated API access, and frontend token lifecycle.
- `agent-harness-etcl`: Testable Execution, Tooling, Context, and Lifecycle modules for realtime agent orchestration.
- `user-session-memory`: User-scoped long-term memory persistence, retrieval, injection into provider context, and retention limits.

### Modified Capabilities

- None.

## Impact

- Affected backend code: FastAPI routers/dependencies, settings, local persistence services, LiveKit session API, agent worker/runtime modules, provider coordination, and tests.
- Affected frontend code: session API client, app state, login/register/logout UI, local storage handling, and tests.
- Affected configuration: `.env.example`, Docker Compose backend environment, and a persistent backend data volume for `/app/data`.
- New local files at runtime: `data/users.json` and `data/memory/<user_id>.jsonl`.
