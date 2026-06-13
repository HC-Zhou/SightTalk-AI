## Why

The current UI requires a manual "voice question" action and a REST turn request for every answer. The target experience is a video-chat style assistant where the user starts once, keeps speaking naturally, and receives realtime captions plus spoken answers driven by the backend media pipeline.

## What Changes

- Start continuous backend-driven listening after a LiveKit session is created.
- Treat microphone audio and camera video as the primary input path; keep `/api/v1/assistant/turn` only as a debug fallback.
- Add realtime event contracts for automatic listening, interruption, assistant audio metadata, and live captions.
- Replace the existing split panel UI with a fixed-height immersive PC web interface.
- Reduce visible controls to Start, End, and Interrupt in the active conversation surface.

## Impact

- Affected specs: `ai-vision-dialog-session`
- Affected code: backend LiveKit agent/session handling, provider event mapping, frontend session hook, frontend app UI, frontend/backend tests
