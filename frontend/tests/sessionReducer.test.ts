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
