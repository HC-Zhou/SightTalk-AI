import type { CapturePolicy, CostSnapshot, ServerEvent } from "../types/events";

export type Message = {
  role: "user" | "assistant";
  text: string;
};

export type SessionState = {
  connectionStatus: "idle" | "connecting" | "ready" | "thinking" | "error";
  policy: CapturePolicy | null;
  messages: Message[];
  assistantDraft: string;
  ttsUrl: string | null;
  cost: CostSnapshot | null;
  errorMessage: string | null;
};

export const initialSessionState: SessionState = {
  connectionStatus: "idle",
  policy: null,
  messages: [],
  assistantDraft: "",
  ttsUrl: null,
  cost: null,
  errorMessage: null
};

export function sessionReducer(state: SessionState, event: ServerEvent): SessionState {
  switch (event.type) {
    case "session.ready":
      return {
        ...state,
        connectionStatus: "ready",
        policy: event.policy,
        errorMessage: null
      };
    case "policy.update":
      return {
        ...state,
        policy: event.policy
      };
    case "transcript.final":
      return {
        ...state,
        messages: [...state.messages, { role: "user", text: event.text }]
      };
    case "assistant.thinking":
      return {
        ...state,
        connectionStatus: "thinking",
        assistantDraft: ""
      };
    case "assistant.text.delta":
      return {
        ...state,
        assistantDraft: state.assistantDraft + event.text
      };
    case "assistant.text.done":
      return {
        ...state,
        connectionStatus: "ready",
        assistantDraft: "",
        messages: [...state.messages, { role: "assistant", text: event.text }]
      };
    case "tts.ready":
      return {
        ...state,
        ttsUrl: event.audio_url
      };
    case "cost.snapshot":
      return {
        ...state,
        cost: {
          frames_captured: event.frames_captured,
          frames_sent_to_model: event.frames_sent_to_model,
          asr_calls: event.asr_calls,
          vision_llm_calls: event.vision_llm_calls,
          tts_calls: event.tts_calls,
          policy: event.policy
        }
      };
    case "error":
      return {
        ...state,
        connectionStatus: "error",
        errorMessage: event.message
      };
  }
}

