## 1. Shared Setup

- [x] 1.1 Read `openspec/changes/add-ai-vision-dialog-assistant/design.md`, `backend/sdd.md`, and `frontend/sdd.md` before implementation.
- [x] 1.2 Create backend and frontend workspaces using the repository conventions in `AGENTS.md`.
- [x] 1.3 Add local development configuration for FastAPI, React/Vite, LiveKit, and the backend agent worker.
- [x] 1.4 Add `.env.example` files documenting LiveKit and Bailian settings without committing secrets.

## 2. Backend Implementation

- [x] 2.1 Scaffold the Python backend package, dependency configuration, lint/type/test tooling, and health route.
- [x] 2.2 Implement settings loading and validation for LiveKit, Bailian, provider selection, and media policy defaults.
- [x] 2.3 Implement `POST /api/v1/livekit/session` and `POST /api/v1/livekit/session/{room_name}/end`.
- [x] 2.4 Implement the LiveKit token service and room/session lifecycle helpers.
- [x] 2.5 Define the `AIProvider` interface and implement `BailianRealtimeProvider`.
- [x] 2.6 Implement the LiveKit agent worker scaffold, cost policy logic, and turn-based Bailian visual assistant bridge.
- [x] 2.7 Add backend unit tests for settings, health, token/session APIs, provider factory behavior, and agent policy logic.

## 3. Frontend Implementation

- [x] 3.1 Scaffold the React/Vite/TypeScript frontend workspace with lint, test, and build scripts.
- [x] 3.2 Implement API client types for the backend session endpoints.
- [x] 3.3 Implement camera and microphone permission handling, local preview, and LiveKit room connection.
- [x] 3.4 Implement the PC web conversation UI with assistant state, transcript, controls, and recoverable error states.
- [x] 3.5 Implement LiveKit data-message handling for assistant events and control messages for mode changes and interruption.
- [x] 3.6 Add frontend tests for permission states, session startup/shutdown, LiveKit event rendering, mode switching, and error display.

## 4. Integration and Verification

- [x] 4.1 Wire `docker compose up --build` to run LiveKit, backend API, backend agent worker, and frontend.
- [x] 4.2 Verify a local browser can start a session, publish microphone/camera tracks, receive assistant events, and stop cleanly.
- [x] 4.3 Run backend checks: `uv run ruff check .`, `uv run mypy`, and `uv run pytest`.
- [x] 4.4 Run frontend checks: `npm run lint`, `npm run test:run`, and `npm run build`.
- [x] 4.5 Document any provider-account limitations or manual setup steps discovered during integration.
