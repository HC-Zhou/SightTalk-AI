export type CapturePolicy = {
  frame_interval_ms: number;
  idle_frame_interval_ms: number;
  image_max_width: number;
  jpeg_quality: number;
  max_keyframes_per_turn: number;
};

export type ClientEvent =
  | { type: "session.start" }
  | { type: "session.stop" }
  | { type: "audio.chunk"; seq: number; mime: string; data: string }
  | { type: "video.frame"; seq: number; mime: string; captured_at: number; data: string }
  | { type: "utterance.end"; audio_seq_end: number }
  | { type: "playback.done" }
  | { type: "client.error"; stage: string; message: string };

export type CostSnapshot = {
  frames_captured: number;
  frames_sent_to_model: number;
  asr_calls: number;
  vision_llm_calls: number;
  tts_calls: number;
  policy: string;
};

export type ServerEvent =
  | { type: "session.ready"; policy: CapturePolicy }
  | { type: "policy.update"; policy: CapturePolicy; reason: string }
  | { type: "transcript.final"; text: string }
  | { type: "assistant.thinking" }
  | { type: "assistant.text.delta"; text: string }
  | { type: "assistant.text.done"; text: string }
  | { type: "tts.ready"; audio_url: string }
  | ({ type: "cost.snapshot" } & CostSnapshot)
  | { type: "error"; stage: string; message: string; retryable: boolean };

