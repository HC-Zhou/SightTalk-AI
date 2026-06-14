export type MediaMode = 'economy' | 'balanced' | 'accurate';

export type AgentStatus =
  | 'connecting'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'interrupted'
  | 'error'
  | 'ended';

export type SessionStatus = 'idle' | 'requesting-permission' | AgentStatus;

export interface CreateLiveKitSessionRequest {
  display_name?: string;
  media_mode?: MediaMode;
}

export interface MediaPolicy {
  mode: MediaMode;
  max_video_fps: number;
  max_jpeg_edge: number;
  jpeg_quality: number;
  vad_enabled: boolean;
}

export interface CreateLiveKitSessionResponse {
  room_name: string;
  participant_identity: string;
  participant_token: string;
  livekit_url: string;
  expires_at: string;
  assistant_identity: string;
  media_policy: MediaPolicy;
}

export interface EndLiveKitSessionRequest {
  participant_identity: string;
}

export interface EndLiveKitSessionResponse {
  status: 'ended';
  room_name: string;
}

export interface AssistantTurnRequest {
  room_name: string;
  prompt: string;
  image_data_url?: string;
  bailian_session_id?: string;
}

export interface AssistantTurnResponse {
  room_name: string;
  text: string;
  bailian_session_id?: string;
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    request_id?: string;
  };
}

export interface BaseRealtimeEvent {
  type: string;
  session_id: string;
  timestamp: string;
  response_epoch?: number;
  response_id?: string;
}

export interface AgentStatusEvent extends BaseRealtimeEvent {
  type: 'agent.status';
  status: AgentStatus;
}

export interface TranscriptDeltaEvent extends BaseRealtimeEvent {
  type: 'transcript.delta';
  speaker: 'user' | 'assistant';
  text: string;
  message_id: string;
}

export interface TranscriptDoneEvent extends BaseRealtimeEvent {
  type: 'transcript.done';
  speaker: 'user' | 'assistant';
  text: string;
  message_id: string;
}

export interface ResponseDoneEvent extends BaseRealtimeEvent {
  type: 'response.done';
  message_id: string;
  audio_playback_complete: boolean;
}

export interface AudioDeltaEvent extends BaseRealtimeEvent {
  type: 'audio.delta';
  message_id: string;
  mime_type: string;
  audio: string;
}

export interface CostEstimateEvent extends BaseRealtimeEvent {
  type: 'cost.estimate';
  audio_seconds: number;
  image_frames_sent: number;
  mode: MediaMode;
}

export interface AgentErrorEvent extends BaseRealtimeEvent {
  type: 'error';
  code: string;
  message: string;
  severity?: 'recoverable' | 'terminal';
  surface?: 'diagnostic' | 'session';
}

export interface DiagnosticErrorEvent extends BaseRealtimeEvent {
  type: 'diagnostic.error';
  diagnostic_id: string;
  severity: 'recoverable' | 'terminal';
  surface: 'diagnostic' | 'session';
  code: string;
  message: string;
}

export interface SessionTerminalEvent extends BaseRealtimeEvent {
  type: 'session.terminal';
  severity: 'terminal';
  surface: 'session';
  code: string;
  message: string;
}

export type RealtimeEvent =
  | AgentStatusEvent
  | TranscriptDeltaEvent
  | TranscriptDoneEvent
  | ResponseDoneEvent
  | AudioDeltaEvent
  | CostEstimateEvent
  | AgentErrorEvent
  | DiagnosticErrorEvent
  | SessionTerminalEvent;

export interface ConversationMessage {
  id: string;
  speaker: 'user' | 'assistant';
  text: string;
  final: boolean;
}

export interface SightTalkError {
  code: string;
  message: string;
  severity?: 'recoverable' | 'terminal';
  surface?: 'diagnostic' | 'session';
}

export interface CostEstimate {
  audioSeconds: number;
  imageFramesSent: number;
  mode: MediaMode;
}
