import { Room, RoomEvent } from 'livekit-client';
import { useCallback, useRef, useState } from 'react';

import { useLocalMedia } from '../media/useLocalMedia';
import { createLiveKitSession, endLiveKitSession, startLiveKitAgentSession } from './api';
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
  assistantAudioActive: boolean;
}

const initialState: SightTalkState = {
  status: 'idle',
  mediaMode: 'balanced',
  messages: [],
  micEnabled: true,
  cameraEnabled: true,
  assistantAudioActive: false,
};

type PublishData = (payload: Uint8Array, options: { reliable: boolean; topic: string }) => void;

export function useSightTalkSession(authToken?: string) {
  const [state, setState] = useState<SightTalkState>(initialState);
  const roomRef = useRef<Room | undefined>(undefined);
  const sessionRef = useRef<CreateLiveKitSessionResponse | undefined>(undefined);
  const assistantAudioElementsRef = useRef<HTMLMediaElement[]>([]);
  const audioMutedByInterruptRef = useRef(false);
  const { stream, requestMedia, stopMedia } = useLocalMedia();

  const pauseAssistantAudio = useCallback(() => {
    audioMutedByInterruptRef.current = true;
    assistantAudioElementsRef.current.forEach((element) => {
      element.muted = true;
      element.pause();
    });
  }, []);

  const resumeAssistantAudio = useCallback(() => {
    if (!audioMutedByInterruptRef.current) {
      return;
    }
    audioMutedByInterruptRef.current = false;
    assistantAudioElementsRef.current.forEach((element) => {
      element.muted = false;
      void element.play().catch(() => {
        // The next user gesture will allow playback if the browser blocks this call.
      });
    });
  }, []);

  const mergeMessage = useCallback((event: Extract<RealtimeEvent, { text: string }>) => {
    setState((current) => {
      const existing = current.messages.find((message) => message.id === event.message_id);
      const text = mergeTranscriptText(existing?.text, event.text, event.type);
      const nextMessage: ConversationMessage = {
        id: event.message_id,
        speaker: event.speaker,
        text,
        final: event.type === 'transcript.done',
      };
      return {
        ...current,
        messages: existing
          ? current.messages.map((message) =>
              message.id === event.message_id
                ? { ...message, text, final: nextMessage.final }
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
          if (event.speaker === 'assistant') {
            resumeAssistantAudio();
          }
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
        case 'audio.delta':
          break;
      }
    },
    [mergeMessage, resumeAssistantAudio],
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
    assistantAudioElementsRef.current.forEach((element) => {
      element.pause();
      element.muted = false;
      element.removeAttribute('src');
      element.load();
      element.remove();
    });
    assistantAudioElementsRef.current = [];
    audioMutedByInterruptRef.current = false;
    if (room) {
      room.off(RoomEvent.DataReceived, handleDataReceived);
      room.disconnect();
    }
    stopMedia();
    if (session && authToken) {
      try {
        await endLiveKitSession(
          session.room_name,
          {
            participant_identity: session.participant_identity,
          },
          authToken,
        );
      } catch {
        // Stop must always release local resources even if backend cleanup fails.
      }
    }
  }, [authToken, handleDataReceived, stopMedia]);

  const start = useCallback(async () => {
    setState((current) => ({ ...current, status: 'requesting-permission', error: undefined }));
    try {
      if (!authToken) {
        throw new Error('Please sign in before starting a session');
      }
      const localStream = await requestMedia();
      setState((current) => ({ ...current, status: 'connecting' }));
      const session = await createLiveKitSession({ media_mode: state.mediaMode }, authToken);
      const room = new Room();
      roomRef.current = room;
      sessionRef.current = session;
      room.on(RoomEvent.DataReceived, handleDataReceived);
      room.on(RoomEvent.TrackSubscribed, (track: unknown) => {
        if (!isAttachableAudioTrack(track)) {
          return;
        }
        const element = track.attach();
        element.autoplay = true;
        element.muted = audioMutedByInterruptRef.current;
        assistantAudioElementsRef.current.push(element);
        document.body.appendChild(element);
        void element.play().catch(() => {
          // Browser autoplay rules can still require a user gesture; the Start click normally satisfies it.
        });
        setState((current) => ({ ...current, assistantAudioActive: true }));
      });
      room.on(RoomEvent.Disconnected, () => {
        setState((current) =>
          current.status === 'ended' ? current : { ...current, status: 'ended' },
        );
      });
      await room.connect(session.livekit_url, session.participant_token);
      await Promise.all(
        localStream.getTracks().map((track) => room.localParticipant.publishTrack(track)),
      );
      void startLiveKitAgentSession(session.room_name, authToken).catch(() => {
        // Real provider sessions may publish their own initial status; this helper is non-critical.
      });
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
  }, [authToken, handleDataReceived, requestMedia, state.mediaMode, stopMedia]);

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
    pauseAssistantAudio();
    setState((current) => ({ ...current, status: 'interrupted' }));
  }, [pauseAssistantAudio]);

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
    toggleMic,
    toggleCamera,
  };
}

function mergeTranscriptText(
  existingText: string | undefined,
  incomingText: string,
  eventType: 'transcript.delta' | 'transcript.done',
) {
  if (!existingText || eventType === 'transcript.done') {
    return incomingText;
  }
  if (incomingText === existingText) {
    return existingText;
  }
  if (incomingText.startsWith(existingText)) {
    return incomingText;
  }
  return `${existingText}${incomingText}`;
}

export function statusLabel(status: SessionStatus | AgentStatus): string {
  const labels: Record<SessionStatus | AgentStatus, string> = {
    idle: 'Idle',
    'requesting-permission': 'Requesting media',
    connecting: 'Connecting',
    listening: 'Listening',
    thinking: 'Thinking',
    speaking: 'Speaking',
    interrupted: 'Interrupted',
    error: 'Error',
    ended: 'Ended',
  };
  return labels[status];
}

interface AttachableAudioTrack {
  kind: string;
  attach: () => HTMLMediaElement;
}

function isAttachableAudioTrack(track: unknown): track is AttachableAudioTrack {
  if (typeof track !== 'object' || track === null) {
    return false;
  }
  const candidate = track as Partial<AttachableAudioTrack>;
  return candidate.kind === 'audio' && typeof candidate.attach === 'function';
}
