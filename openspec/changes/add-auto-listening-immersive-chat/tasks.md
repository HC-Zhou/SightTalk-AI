## 1. OpenSpec

- [x] 1.1 Create proposal, design, tasks, and delta spec for automatic listening and immersive chat.

## 2. Backend

- [x] 2.1 Extend provider events and backend event mapping for assistant audio metadata and interrupted status.
- [x] 2.2 Add automatic session-start event support so active rooms enter listening without manual REST turns.
- [x] 2.3 Add tests for automatic listening events, interrupt handling, and provider audio event mapping.

## 3. Frontend

- [x] 3.1 Remove browser speech recognition, text composer, media mode controls, and camera/mic toggle buttons from the main UI.
- [x] 3.2 Update the session hook so LiveKit data events and remote audio are the primary conversation path.
- [x] 3.3 Redesign the app as a fixed-height immersive PC video chat interface with Start, End, and Interrupt only.
- [x] 3.4 Update frontend tests for automatic listening, captions, controls, and removal of old manual controls.

## 4. Verification

- [x] 4.1 Run backend lint, type checks, and tests.
- [x] 4.2 Run frontend lint, tests, and production build.
