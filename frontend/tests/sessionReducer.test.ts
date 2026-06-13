import { describe, expect, it } from "vitest";
import { initialSessionState, sessionReducer } from "../src/shared/sessionReducer";
import type { ServerEvent } from "../src/types/events";

describe("sessionReducer", () => {
  it("stores ready policy", () => {
    const event: ServerEvent = {
      type: "session.ready",
      policy: {
        frame_interval_ms: 2000,
        idle_frame_interval_ms: 5000,
        image_max_width: 640,
        jpeg_quality: 0.7,
        max_keyframes_per_turn: 3
      }
    };

    const state = sessionReducer(initialSessionState, event);

    expect(state.connectionStatus).toBe("ready");
    expect(state.policy?.max_keyframes_per_turn).toBe(3);
  });

  it("adds transcript and assistant response", () => {
    let state = sessionReducer(initialSessionState, {
      type: "transcript.final",
      text: "What am I holding?"
    });
    state = sessionReducer(state, { type: "assistant.text.done", text: "A mug." });

    expect(state.messages).toEqual([
      { role: "user", text: "What am I holding?" },
      { role: "assistant", text: "A mug." }
    ]);
  });

  it("tracks assistant thinking as a live subtitle state", () => {
    const state = sessionReducer(initialSessionState, { type: "assistant.thinking" });

    expect(state.liveSubtitle).toEqual({
      speaker: "assistant",
      text: "",
      phase: "thinking"
    });
  });

  it("streams assistant deltas into the assistant draft and live subtitle", () => {
    let state = sessionReducer(initialSessionState, { type: "assistant.text.delta", text: "I see" });
    state = sessionReducer(state, { type: "assistant.text.delta", text: " a keyboard" });

    expect(state.assistantDraft).toBe("I see a keyboard");
    expect(state.liveSubtitle).toEqual({
      speaker: "assistant",
      text: "I see a keyboard",
      phase: "streaming"
    });
  });

  it("keeps assistant final text as the latest live subtitle", () => {
    let state = sessionReducer(initialSessionState, { type: "assistant.text.delta", text: "A laptop" });
    state = sessionReducer(state, { type: "assistant.text.done", text: "A laptop is on the desk." });

    expect(state.messages).toEqual([{ role: "assistant", text: "A laptop is on the desk." }]);
    expect(state.liveSubtitle).toEqual({
      speaker: "assistant",
      text: "A laptop is on the desk.",
      phase: "final"
    });
  });

  it("shows final user transcript as the latest live subtitle", () => {
    const state = sessionReducer(initialSessionState, {
      type: "transcript.final",
      text: "Describe the app icons."
    });

    expect(state.liveSubtitle).toEqual({
      speaker: "user",
      text: "Describe the app icons.",
      phase: "final"
    });
  });

  it("stores structured server errors for the subtitle rail", () => {
    const state = sessionReducer(initialSessionState, {
      type: "error",
      stage: "asr",
      message: "Audio decode failed",
      retryable: true
    });

    expect(state.errorMessage).toBe("Audio decode failed");
    expect(state.lastError).toEqual({
      stage: "asr",
      message: "Audio decode failed",
      retryable: true
    });
  });

  it("stores tts url and cost snapshot", () => {
    let state = sessionReducer(initialSessionState, {
      type: "tts.ready",
      audio_url: "/api/v1/audio/x.wav"
    });
    state = sessionReducer(state, {
      type: "cost.snapshot",
      frames_captured: 4,
      frames_sent_to_model: 2,
      asr_calls: 1,
      vision_llm_calls: 1,
      tts_calls: 1,
      policy: "normal"
    });

    expect(state.ttsUrl).toBe("/api/v1/audio/x.wav");
    expect(state.cost?.frames_sent_to_model).toBe(2);
  });
});
