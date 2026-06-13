## Context

SightTalk already provisions LiveKit rooms and publishes browser camera/microphone tracks. The missing product behavior is automatic turn detection and response playback without a frontend speech-recognition button. The new implementation keeps LiveKit as the media transport and moves speech/vision understanding to the backend/provider side.

## Goals

- Enter continuous listening immediately after `开始对话`.
- Let backend/provider VAD decide when the user has finished an utterance.
- Send policy-limited camera frames with the utterance context.
- Render user and assistant subtitles in realtime.
- Play assistant audio from the room or provider-driven audio events.
- Keep the active PC web UI full viewport height with only Start, End, and Interrupt visible as primary controls.

## Non-Goals

- Mobile adaptation.
- Replacing LiveKit with a browser-to-provider direct connection.
- Removing the existing REST turn endpoint.
- Copying proprietary Doubao assets or layouts pixel-for-pixel.

## Decisions

1. Backend owns ASR and end-of-speech detection.
   - The frontend publishes microphone audio to LiveKit and subscribes to `sighttalk.agent` data messages.
   - Provider events are normalized into `transcript.delta`, `transcript.done`, `agent.status`, `response.done`, and `audio.delta`.

2. Camera sampling is backend policy driven.
   - Balanced mode samples roughly 1 FPS during active speech or visual-intent windows.
   - The browser no longer captures still frames for every manual prompt.

3. The frontend treats the room as an always-on conversation.
   - `Listening` is the normal active state.
   - `Thinking` and `Speaking` are rendered from backend status events.
   - `Interrupt` publishes `client.interrupt` and locally returns the UI to listening while awaiting backend confirmation.

4. Assistant audio is room-first.
   - The preferred path is an assistant audio track published into LiveKit.
   - `audio.delta` events are supported as metadata/test hooks and future fallback.

5. UI is immersive but operational.
   - Full-bleed camera preview is the primary canvas.
   - Captions float over the video with a compact transcript rail.
   - Bottom controls remain fixed and simple.

## Risks

- Real provider VAD/audio output behavior can vary by Bailian model. Keep provider wire mapping isolated.
- Local mock mode cannot perform true ASR. It should still demonstrate automatic session state, captions, and controls without the old manual button.
- LiveKit Python RTC support requires the `livekit` package in addition to `livekit-api`.
