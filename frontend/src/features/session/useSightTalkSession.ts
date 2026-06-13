import { Room, RoomEvent } from 'livekit-client';
import { useCallback, useRef, useState } from 'react';

import { useLocalMedia } from '../media/useLocalMedia';
import { createAssistantTurn, createLiveKitSession, endLiveKitSession } from './api';
import {
  AGENT_TOPIC,
  CONTROL_TOPIC,
  decodeRealtimeEvent,
  encodeInterrupt,
  encodeModeUpdate,
} from './livekitEvents';
import type {
  AgentStatus,
  ConversationMessage,
  CostEstimate,
  CreateLiveKitSessionResponse,
  MediaMode,
  RealtimeEvent,
  SessionStatus,
  SightTalkError,
} from './types';

interface SightTalkState {
  status: SessionStatus;
  mediaMode: MediaMode;
  session?: CreateLiveKitSessionResponse;
  messages: ConversationMessage[];
  cost?: CostEstimate;
  error?: SightTalkError;
  micEnabled: boolean;
  cameraEnabled: boolean;
}

const initialState: SightTalkState = {
  status: 'idle',
  mediaMode: 'balanced',
  messages: [],
  micEnabled: true,
  cameraEnabled: true,
};

type PublishData = (payload: Uint8Array, options: { reliable: boolean; topic: string }) => void;

export function useSightTalkSession() {
  const [state, setState] = useState<SightTalkState>(initialState);
  const roomRef = useRef<Room | undefined>(undefined);
  const sessionRef = useRef<CreateLiveKitSessionResponse | undefined>(undefined);
  const bailianSessionIdRef = useRef<string | undefined>(undefined);
  const { stream, requestMedia, stopMedia } = useLocalMedia();

  const mergeMessage = useCallback((event: Extract<RealtimeEvent, { text: string }>) => {
    setState((current) => {
      const existing = current.messages.find((message) => message.id === event.message_id);
      const nextMessage: ConversationMessage = {
        id: event.message_id,
        speaker: event.speaker,
        text: event.text,
        final: event.type === 'transcript.done',
      };
      return {
        ...current,
        messages: existing
          ? current.messages.map((message) =>
              message.id === event.message_id
                ? { ...message, text: event.text, final: nextMessage.final }
                : message,
            )
          : [...current.messages, nextMessage],
      };
    });
  }, []);

  const applyRealtimeEvent = useCallback(
    (event: RealtimeEvent) => {
      switch (event.type) {
        case 'agent.status':
          setState((current) => ({ ...current, status: event.status }));
          break;
        case 'transcript.delta':
        case 'transcript.done':
          mergeMessage(event);
          break;
        case 'cost.estimate':
          setState((current) => ({
            ...current,
            cost: {
              audioSeconds: event.audio_seconds,
              imageFramesSent: event.image_frames_sent,
              mode: event.mode,
            },
          }));
          break;
        case 'error':
          setState((current) => ({
            ...current,
            status: 'error',
            error: { code: event.code, message: event.message },
          }));
          break;
        case 'response.done':
          break;
      }
    },
    [mergeMessage],
  );

  const handleDataReceived = useCallback(
    (...args: unknown[]) => {
      const payload = args.find((arg): arg is ArrayBufferView => ArrayBuffer.isView(arg));
      const topic = args.find((arg): arg is string => typeof arg === 'string');
      if (!ArrayBuffer.isView(payload) || topic !== AGENT_TOPIC) {
        return;
      }
      const event = decodeRealtimeEvent(
        new Uint8Array(payload.buffer, payload.byteOffset, payload.byteLength),
      );
      if (event) {
        applyRealtimeEvent(event);
      }
    },
    [applyRealtimeEvent],
  );

  const cleanup = useCallback(async () => {
    const room = roomRef.current;
    const session = sessionRef.current;
    roomRef.current = undefined;
    sessionRef.current = undefined;
    bailianSessionIdRef.current = undefined;
    if (room) {
      room.off(RoomEvent.DataReceived, handleDataReceived);
      room.disconnect();
    }
    stopMedia();
    if (session) {
      try {
        await endLiveKitSession(session.room_name, {
          participant_identity: session.participant_identity,
        });
      } catch {
        // Stop must always release local resources even if backend cleanup fails.
      }
    }
  }, [handleDataReceived, stopMedia]);

  const start = useCallback(async () => {
    setState((current) => ({ ...current, status: 'requesting-permission', error: undefined }));
    try {
      const localStream = await requestMedia();
      setState((current) => ({ ...current, status: 'connecting' }));
      const session = await createLiveKitSession({ media_mode: state.mediaMode });
      const room = new Room();
      roomRef.current = room;
      sessionRef.current = session;
      room.on(RoomEvent.DataReceived, handleDataReceived);
      room.on(RoomEvent.Disconnected, () => {
        setState((current) =>
          current.status === 'ended' ? current : { ...current, status: 'ended' },
        );
      });
      await room.connect(session.livekit_url, session.participant_token);
      await Promise.all(
        localStream.getTracks().map((track) => room.localParticipant.publishTrack(track)),
      );
      setState((current) => ({
        ...current,
        status: 'listening',
        session,
        error: undefined,
      }));
    } catch (error) {
      stopMedia();
      setState((current) => ({
        ...current,
        status: 'error',
        error: {
          code: 'SESSION_START_FAILED',
          message: error instanceof Error ? error.message : 'Unable to start session',
        },
      }));
    }
  }, [handleDataReceived, requestMedia, state.mediaMode, stopMedia]);

  const stop = useCallback(async () => {
    await cleanup();
    setState((current) => ({ ...current, status: 'ended', session: undefined }));
  }, [cleanup]);

  const setMediaMode = useCallback((mode: MediaMode) => {
    setState((current) => ({ ...current, mediaMode: mode }));
    const session = sessionRef.current;
    const room = roomRef.current;
    if (session && room) {
      const publishData = room.localParticipant.publishData as unknown as PublishData;
      publishData(encodeModeUpdate(session.room_name, mode), {
        reliable: true,
        topic: CONTROL_TOPIC,
      });
    }
  }, []);

  const interrupt = useCallback(() => {
    const session = sessionRef.current;
    const room = roomRef.current;
    if (!session || !room) {
      return;
    }
    const publishData = room.localParticipant.publishData as unknown as PublishData;
    publishData(encodeInterrupt(session.room_name), {
      reliable: true,
      topic: CONTROL_TOPIC,
    });
  }, []);

  const sendTurn = useCallback(async (prompt: string, imageDataUrl?: string) => {
    const session = sessionRef.current;
    const text = prompt.trim();
    if (!session || !text) {
      return;
    }
    const userMessageId = `user-${Date.now()}`;
    setState((current) => ({
      ...current,
      status: 'thinking',
      error: undefined,
      messages: [
        ...current.messages,
        { id: userMessageId, speaker: 'user', text, final: true },
      ],
    }));
    try {
      const response = await createAssistantTurn({
        room_name: session.room_name,
        prompt: text,
        image_data_url: imageDataUrl,
        bailian_session_id: bailianSessionIdRef.current,
      });
      bailianSessionIdRef.current = response.bailian_session_id;
      const assistantMessageId = `assistant-${Date.now()}`;
      setState((current) => ({
        ...current,
        status: 'listening',
        messages: [
          ...current.messages,
          { id: assistantMessageId, speaker: 'assistant', text: response.text, final: true },
        ],
        cost: {
          audioSeconds: current.cost?.audioSeconds ?? 0,
          imageFramesSent: (current.cost?.imageFramesSent ?? 0) + (imageDataUrl ? 1 : 0),
          mode: current.mediaMode,
        },
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        status: 'error',
        error: {
          code: 'ASSISTANT_TURN_FAILED',
          message: error instanceof Error ? error.message : 'Assistant request failed',
        },
      }));
    }
  }, []);

  const toggleMic = useCallback(() => {
    const enabled = !state.micEnabled;
    stream?.getAudioTracks().forEach((track) => {
      track.enabled = enabled;
    });
    setState((current) => ({ ...current, micEnabled: enabled }));
  }, [state.micEnabled, stream]);

  const toggleCamera = useCallback(() => {
    const enabled = !state.cameraEnabled;
    stream?.getVideoTracks().forEach((track) => {
      track.enabled = enabled;
    });
    setState((current) => ({ ...current, cameraEnabled: enabled }));
  }, [state.cameraEnabled, stream]);

  return {
    ...state,
    localPreviewStream: stream,
    start,
    stop,
    setMediaMode,
    interrupt,
    sendTurn,
    toggleMic,
    toggleCamera,
  };
}

export function statusLabel(status: SessionStatus | AgentStatus): string {
  const labels: Record<SessionStatus | AgentStatus, string> = {
    idle: 'Idle',
    'requesting-permission': 'Requesting media',
    connecting: 'Connecting',
    listening: 'Listening',
    thinking: 'Thinking',
    speaking: 'Speaking',
    error: 'Error',
    ended: 'Ended',
  };
  return labels[status];
}
