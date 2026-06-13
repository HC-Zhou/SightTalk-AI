import type { CapturePolicy, CostSnapshot, ServerEvent } from "../types/events";

export type Message = {
  role: "user" | "assistant";
  text: string;
};

export type LiveSubtitle = {
  speaker: "user" | "assistant";
  text: string;
  phase: "listening" | "thinking" | "streaming" | "final";
};

export type SessionError = {
  stage: string;
  message: string;
  retryable: boolean;
};

export type SessionState = {
  connectionStatus: "idle" | "connecting" | "ready" | "thinking" | "error";
  policy: CapturePolicy | null;
  messages: Message[];
  assistantDraft: string;
  liveSubtitle: LiveSubtitle | null;
  ttsUrl: string | null;
  cost: CostSnapshot | null;
  errorMessage: string | null;
  lastError: SessionError | null;
};

export const initialSessionState: SessionState = {
  connectionStatus: "idle",
  policy: null,
  messages: [],
  assistantDraft: "",
  liveSubtitle: null,
  ttsUrl: null,
  cost: null,
  errorMessage: null,
  lastError: null
};

export function sessionReducer(state: SessionState, event: ServerEvent): SessionState {
  switch (event.type) {
    case "session.ready":
      return {
        ...state,
        connectionStatus: "ready",
        policy: event.policy,
        errorMessage: null,
        lastError: null
      };
    case "policy.update":
      return {
        ...state,
        policy: event.policy
      };
    case "transcript.final":
      return {
        ...state,
        messages: [...state.messages, { role: "user", text: event.text }],
        liveSubtitle: {
          speaker: "user",
          text: event.text,
          phase: "final"
        }
      };
    case "assistant.thinking":
      return {
        ...state,
        connectionStatus: "thinking",
        assistantDraft: "",
        liveSubtitle: {
          speaker: "assistant",
          text: "",
          phase: "thinking"
        }
      };
    case "assistant.text.delta": {
      const assistantDraft = state.assistantDraft + event.text;
      return {
        ...state,
        assistantDraft,
        liveSubtitle: {
          speaker: "assistant",
          text: assistantDraft,
          phase: "streaming"
        }
      };
    }
    case "assistant.text.done":
      return {
        ...state,
        connectionStatus: "ready",
        assistantDraft: "",
        messages: [...state.messages, { role: "assistant", text: event.text }],
        liveSubtitle: {
          speaker: "assistant",
          text: event.text,
          phase: "final"
        }
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
        errorMessage: event.message,
        lastError: {
          stage: event.stage,
          message: event.message,
          retryable: event.retryable
        }
      };
  }
}
