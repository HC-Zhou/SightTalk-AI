# Frontend Video Chat Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the React frontend into a Doubao-style PC web video chat interface while preserving the existing backend WebSocket event protocol.

**Architecture:** Centralize API URL construction in `apiConfig`, make `VisionSessionClient` own session WebSocket lifecycle and parse errors, extend `sessionReducer` with live subtitle state, then replace the panel demo UI with a video-stage layout and subtitle rail. Existing media hooks stay in place.

**Tech Stack:** React 18, TypeScript, Vite, Vitest, Testing Library, ESLint, lucide-react.

---

## Source References

- Design spec: `docs/superpowers/specs/2026-06-13-frontend-video-chat-modernization-design.md`
- Backend WebSocket route: `backend/src/sighttalk_api/api/v1/websocket.py`
- Event types: `frontend/src/types/events.ts`
- Current app entry: `frontend/src/App.tsx`
- Current client wrapper: `frontend/src/shared/wsClient.ts`
- Current reducer: `frontend/src/shared/sessionReducer.ts`

## File Structure

Files to create:

- `frontend/src/shared/apiConfig.ts`: API origin, WebSocket URL, and asset URL helpers.
- `frontend/tests/apiConfig.test.ts`: URL helper tests.

Files to modify:

- `frontend/src/shared/wsClient.ts`: session-based WebSocket lifecycle, safe parsing, send return value, close reason handling.
- `frontend/tests/wsClient.test.ts`: WebSocket lifecycle and error tests.
- `frontend/src/shared/sessionReducer.ts`: live subtitle state and richer error state.
- `frontend/tests/sessionReducer.test.ts`: live subtitle reducer tests.
- `frontend/src/App.tsx`: video call shell, controls, subtitle rail, audio URL resolution.
- `frontend/src/App.css`: Doubao-style PC landscape layout and responsive states.

Files to leave unchanged unless a test proves they need adjustment:

- `frontend/src/hooks/useCameraSampler.ts`
- `frontend/src/hooks/useMicrophoneRecorder.ts`
- `frontend/src/types/events.ts`

---

### Task 1: Add API URL configuration

**Files:**

- Create: `frontend/src/shared/apiConfig.ts`
- Create: `frontend/tests/apiConfig.test.ts`

- [ ] **Step 1: Write the failing API config tests**

Create `frontend/tests/apiConfig.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  buildSessionWebSocketUrl,
  createApiConfig,
  resolveApiAssetUrl
} from "../src/shared/apiConfig";

describe("apiConfig", () => {
  it("uses localhost defaults for development", () => {
    const config = createApiConfig({});

    expect(config.apiOrigin).toBe("http://127.0.0.1:8000");
    expect(config.wsOrigin).toBe("ws://127.0.0.1:8000");
  });

  it("derives secure websocket origin from https API origin", () => {
    const config = createApiConfig({ VITE_API_ORIGIN: "https://api.example.com/" });

    expect(config.apiOrigin).toBe("https://api.example.com");
    expect(config.wsOrigin).toBe("wss://api.example.com");
  });

  it("builds encoded session websocket URLs", () => {
    const config = createApiConfig({ VITE_API_ORIGIN: "https://api.example.com" });

    expect(buildSessionWebSocketUrl("demo/session", config)).toBe(
      "wss://api.example.com/ws/session/demo%2Fsession"
    );
  });

  it("resolves relative API assets against the HTTP origin", () => {
    const config = createApiConfig({ VITE_API_ORIGIN: "https://api.example.com" });

    expect(resolveApiAssetUrl("/api/v1/audio/a.wav", config)).toBe(
      "https://api.example.com/api/v1/audio/a.wav"
    );
    expect(resolveApiAssetUrl("https://cdn.example.com/a.wav", config)).toBe(
      "https://cdn.example.com/a.wav"
    );
  });
});
```

- [ ] **Step 2: Run the API config test and verify RED**

Run:

```bash
cd frontend
npm run test:run -- tests/apiConfig.test.ts
```

Expected: FAIL because `../src/shared/apiConfig` does not exist.

- [ ] **Step 3: Implement API config helpers**

Create `frontend/src/shared/apiConfig.ts` with these exports:

```ts
export type ApiConfig = {
  apiOrigin: string;
  wsOrigin: string;
};

export type ApiEnv = {
  VITE_API_ORIGIN?: string;
};

const DEFAULT_API_ORIGIN = "http://127.0.0.1:8000";

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function deriveWebSocketOrigin(apiOrigin: string): string {
  const url = new URL(apiOrigin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return trimTrailingSlash(url.toString());
}

export function createApiConfig(env: ApiEnv = import.meta.env): ApiConfig {
  const apiOrigin = trimTrailingSlash(env.VITE_API_ORIGIN?.trim() || DEFAULT_API_ORIGIN);
  return {
    apiOrigin,
    wsOrigin: deriveWebSocketOrigin(apiOrigin)
  };
}

export function buildSessionWebSocketUrl(sessionId: string, config = createApiConfig()): string {
  return `${config.wsOrigin}/ws/session/${encodeURIComponent(sessionId)}`;
}

export function resolveApiAssetUrl(pathOrUrl: string, config = createApiConfig()): string {
  return new URL(pathOrUrl, `${config.apiOrigin}/`).toString();
}
```

- [ ] **Step 4: Run the API config test and verify GREEN**

Run:

```bash
cd frontend
npm run test:run -- tests/apiConfig.test.ts
```

Expected: PASS with 4 tests.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add frontend/src/shared/apiConfig.ts frontend/tests/apiConfig.test.ts
git commit -m "feat(frontend): 新增 API 地址配置"
```

---

### Task 2: Refactor WebSocket client lifecycle

**Files:**

- Modify: `frontend/src/shared/wsClient.ts`
- Modify: `frontend/tests/wsClient.test.ts`

- [ ] **Step 1: Replace WebSocket tests with lifecycle coverage**

Replace `frontend/tests/wsClient.test.ts` with tests that assert:

- constructor takes `sessionId` and builds the URL from `apiConfig`
- `connect()` emits `connecting`, then `open`, then sends `session.start`
- `send()` returns `true` when open and `false` when closed
- invalid JSON triggers `onClientError` and `error` status
- `close()` sends `session.stop` before closing an open socket

- [ ] **Step 2: Run WebSocket tests and verify RED**

Run:

```bash
cd frontend
npm run test:run -- tests/wsClient.test.ts
```

Expected: FAIL because current `VisionSessionClient` still requires a raw `url`, `send()` returns `void`, and invalid JSON is not handled.

- [ ] **Step 3: Implement session-based WebSocket client**

Update `frontend/src/shared/wsClient.ts` so:

- `VisionSessionClientOptions` includes `sessionId`, optional `apiConfig`, `onEvent`, `onStatus`, optional `onClientError`.
- `connect()` uses `buildSessionWebSocketUrl(sessionId, apiConfig)`.
- `onmessage` wraps `JSON.parse` in `try/catch`.
- `send(event)` returns `false` unless `readyState === WebSocket.OPEN`; otherwise it sends JSON and returns `true`.
- `close()` sends `{ type: "session.stop" }` only when the socket is open, then closes and clears the socket.
- `onclose` reports `closed` for normal close and `error` for non-normal close codes.

- [ ] **Step 4: Run WebSocket tests and verify GREEN**

Run:

```bash
cd frontend
npm run test:run -- tests/wsClient.test.ts
```

Expected: PASS.

- [ ] **Step 5: Run API and WebSocket tests together**

Run:

```bash
cd frontend
npm run test:run -- tests/apiConfig.test.ts tests/wsClient.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add frontend/src/shared/wsClient.ts frontend/tests/wsClient.test.ts
git commit -m "feat(frontend): 优化 WebSocket 会话客户端"
```

---

### Task 3: Add live subtitle state

**Files:**

- Modify: `frontend/src/shared/sessionReducer.ts`
- Modify: `frontend/tests/sessionReducer.test.ts`

- [ ] **Step 1: Add failing reducer tests**

Extend `frontend/tests/sessionReducer.test.ts` with tests that assert:

- `assistant.thinking` sets `liveSubtitle.phase` to `thinking`.
- repeated `assistant.text.delta` appends `assistantDraft` and updates assistant live subtitle text.
- `assistant.text.done` finalizes the assistant message and leaves a final assistant live subtitle.
- `transcript.final` appends a user message and displays final user live subtitle.
- server `error` stores `stage`, `message`, and `retryable` in `lastError`.

- [ ] **Step 2: Run reducer tests and verify RED**

Run:

```bash
cd frontend
npm run test:run -- tests/sessionReducer.test.ts
```

Expected: FAIL because `liveSubtitle` and `lastError` do not exist.

- [ ] **Step 3: Implement subtitle reducer state**

Update `frontend/src/shared/sessionReducer.ts`:

- Add `LiveSubtitle` type with `speaker`, `text`, and `phase`.
- Add `SessionError` type with `stage`, `message`, and `retryable`.
- Add `liveSubtitle: LiveSubtitle | null` and `lastError: SessionError | null` to `SessionState`.
- Preserve existing `errorMessage` for current callers.
- Update reducer cases according to the design spec.

- [ ] **Step 4: Run reducer tests and verify GREEN**

Run:

```bash
cd frontend
npm run test:run -- tests/sessionReducer.test.ts
```

Expected: PASS.

- [ ] **Step 5: Run all focused state/client tests**

Run:

```bash
cd frontend
npm run test:run -- tests/apiConfig.test.ts tests/wsClient.test.ts tests/sessionReducer.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add frontend/src/shared/sessionReducer.ts frontend/tests/sessionReducer.test.ts
git commit -m "feat(frontend): 新增实时字幕状态"
```

---

### Task 4: Build the PC video chat interface

**Files:**

- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.css`
- Modify: `frontend/tests/sessionReducer.test.ts` only if component-facing state assertions need adjustment.

- [ ] **Step 1: Implement the video call shell**

Update `frontend/src/App.tsx` to:

- Use `createApiConfig()` and `resolveApiAssetUrl()` for audio playback.
- Construct `VisionSessionClient` with `sessionId: "demo-session"` instead of a raw URL.
- Keep `useCameraSampler` and `useMicrophoneRecorder`.
- Render a full viewport video call shell:
  - top compact status overlay
  - main `video` stage using `camera.videoRef`
  - center/bottom `liveSubtitle` overlay
  - bottom circular buttons for mic/session start, utterance end, screen/upload action, and hangup
  - right subtitle rail with live subtitle, recent message history, cost, and errors
- Disable utterance/end buttons when no client is open.
- Show camera and microphone errors in the right rail without breaking layout.

- [ ] **Step 2: Implement Doubao-style PC CSS**

Update `frontend/src/App.css` to:

- Remove the old dashboard grid appearance from the first screen.
- Use a warm, real-camera-like stage background instead of black blocks.
- Use stable dimensions for bottom circular controls.
- Use a two-column layout above `1100px`.
- Collapse the subtitle rail under the stage below `1100px`.
- Keep controls readable and non-overlapping below `768px`.
- Avoid nested cards and marketing hero copy.

- [ ] **Step 3: Run TypeScript/build feedback**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 4: Commit Task 4**

Run:

```bash
git add frontend/src/App.tsx frontend/src/App.css
git commit -m "feat(frontend): 重做视频对话页面体验"
```

---

### Task 5: Final verification and browser check

**Files:**

- No planned source edits unless verification reveals a defect.

- [ ] **Step 1: Run full frontend verification**

Run:

```bash
cd frontend
npm run lint
npm run test:run
npm run build
```

Expected:

- ESLint exits 0 with `--max-warnings=0`.
- Vitest reports all test files passing.
- Vite build exits 0.

- [ ] **Step 2: Start the frontend dev server**

Run:

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

Expected: Vite prints a localhost URL.

- [ ] **Step 3: Browser visual verification**

Open the Vite URL in the browser and verify:

- desktop landscape: video stage is not a black blank area
- desktop landscape: right subtitle rail is visible
- bottom controls are circular, aligned, and do not overlap subtitles
- mobile/narrow viewport: rail stacks cleanly and controls remain readable

- [ ] **Step 4: Commit any verification fixes**

If Step 3 requires source fixes, commit them with:

```bash
git add frontend/src/App.tsx frontend/src/App.css frontend/tests
git commit -m "fix(frontend): 修复视频对话页面响应式问题"
```

If no fixes are needed, do not create an empty commit.

## Self Review

- Spec coverage: API config is Task 1, WebSocket lifecycle is Task 2, subtitle state is Task 3, page experience is Task 4, verification is Task 5.
- No backend protocol changes are included.
- User-side live subtitle limitation is handled by reducer state and UI copy through final transcript events.
- No provider/API key controls are exposed in frontend.
- Tasks are ordered so tests are written before production code for behavior changes.
