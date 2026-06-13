import type { MediaMode, RealtimeEvent } from './types';

export const AGENT_TOPIC = 'sighttalk.agent';
export const CONTROL_TOPIC = 'sighttalk.control';

export function decodeRealtimeEvent(payload: Uint8Array): RealtimeEvent | null {
  try {
    const text = new TextDecoder().decode(payload);
    const event = JSON.parse(text) as RealtimeEvent;
    if (!event.type || !event.session_id || !event.timestamp) {
      return null;
    }
    return event;
  } catch {
    return null;
  }
}

export function encodeModeUpdate(sessionId: string, mode: MediaMode): Uint8Array {
  return encodeJson({
    type: 'client.mode.update',
    session_id: sessionId,
    timestamp: new Date().toISOString(),
    mode,
  });
}

export function encodeInterrupt(sessionId: string): Uint8Array {
  return encodeJson({
    type: 'client.interrupt',
    session_id: sessionId,
    timestamp: new Date().toISOString(),
  });
}

function encodeJson(payload: unknown): Uint8Array {
  return new TextEncoder().encode(JSON.stringify(payload));
}
