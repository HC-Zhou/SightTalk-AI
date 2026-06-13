import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';

interface MockRoom {
  connect: ReturnType<typeof vi.fn>;
  disconnect: ReturnType<typeof vi.fn>;
  localParticipant: {
    publishTrack: ReturnType<typeof vi.fn>;
    publishData: ReturnType<typeof vi.fn>;
  };
  emitData: (payload: unknown, topic?: string) => void;
  emitTrackSubscribed: (track: unknown) => void;
}

interface LiveKitMockModule {
  __mockRooms: MockRoom[];
}

vi.mock('livekit-client', () => {
  const rooms: MockRoom[] = [];
  const RoomEvent = {
    DataReceived: 'dataReceived',
    Disconnected: 'disconnected',
    TrackSubscribed: 'trackSubscribed',
  };

  class Room {
    private listeners = new Map<string, Array<(...args: unknown[]) => void>>();

    localParticipant = {
      publishTrack: vi.fn().mockResolvedValue(undefined),
      publishData: vi.fn(),
    };

    connect = vi.fn().mockResolvedValue(undefined);

    disconnect = vi.fn(() => {
      this.listeners.get(RoomEvent.Disconnected)?.forEach((listener) => listener());
    });

    constructor() {
      rooms.push(this as unknown as MockRoom);
    }

    on(event: string, listener: (...args: unknown[]) => void) {
      const existing = this.listeners.get(event) ?? [];
      this.listeners.set(event, [...existing, listener]);
      return this;
    }

    off(event: string, listener: (...args: unknown[]) => void) {
      const existing = this.listeners.get(event) ?? [];
      this.listeners.set(
        event,
        existing.filter((candidate) => candidate !== listener),
      );
      return this;
    }

    emitData(payload: unknown, topic = 'sighttalk.agent') {
      const bytes = new TextEncoder().encode(JSON.stringify(payload));
      this.listeners
        .get(RoomEvent.DataReceived)
        ?.forEach((listener) => listener(bytes, undefined, undefined, topic));
    }

    emitTrackSubscribed(track: unknown) {
      this.listeners.get(RoomEvent.TrackSubscribed)?.forEach((listener) => listener(track));
    }
  }

  return { Room, RoomEvent, __mockRooms: rooms };
});

function createTrack(kind: 'audio' | 'video') {
  return {
    kind,
    enabled: true,
    stop: vi.fn(),
  } as unknown as MediaStreamTrack;
}

function createStream() {
  const audio = createTrack('audio');
  const video = createTrack('video');
  return {
    audio,
    video,
    stream: {
      getTracks: () => [audio, video],
      getAudioTracks: () => [audio],
      getVideoTracks: () => [video],
    } as unknown as MediaStream,
  };
}

function mockSessionFetch() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith('/api/v1/livekit/session')) {
      return new Response(
        JSON.stringify({
          room_name: 'sighttalk-test',
          participant_identity: 'user-test',
          participant_token: 'token',
          livekit_url: 'ws://localhost:7880',
          expires_at: '2026-06-13T12:00:00Z',
          assistant_identity: 'assistant-sighttalk-test',
          media_policy: {
            mode: 'balanced',
            max_video_fps: 1,
            max_jpeg_edge: 1024,
            jpeg_quality: 75,
            vad_enabled: true,
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      );
    }
    if (url.endsWith('/api/v1/livekit/session/sighttalk-test/agent/start')) {
      return new Response(JSON.stringify({ status: 'started', room_name: 'sighttalk-test' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response(JSON.stringify({ status: 'ended', room_name: 'sighttalk-test' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });
}

async function latestRoom() {
  const module = (await import('livekit-client')) as unknown as LiveKitMockModule;
  return module.__mockRooms[module.__mockRooms.length - 1];
}

beforeEach(async () => {
  const module = (await import('livekit-client')) as unknown as LiveKitMockModule;
  module.__mockRooms.length = 0;
  vi.stubGlobal('fetch', mockSessionFetch());
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('App', () => {
  it('renders automatic conversation entry without manual turn controls', () => {
    render(<App />);

    expect(screen.getByRole('heading', { name: '视频对话助手' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '开始' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '开始对话' })).not.toBeInTheDocument();
    expect(screen.queryByText('语音提问')).not.toBeInTheDocument();
    expect(screen.queryByText('发送')).not.toBeInTheDocument();
    expect(screen.queryByText('Accurate')).not.toBeInTheDocument();
  });

  it('shows recoverable error when media permission is denied', async () => {
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn().mockRejectedValue(new Error('Permission denied')),
      },
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: '开始' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Permission denied');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('starts LiveKit and automatically starts the backend agent', async () => {
    const { stream } = createStream();
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue(stream),
      },
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: '开始' }));

    expect(await screen.findByText('Listening')).toBeInTheDocument();
    const room = await latestRoom();
    expect(room.connect).toHaveBeenCalledWith('ws://localhost:7880', 'token');
    expect(room.localParticipant.publishTrack).toHaveBeenCalledTimes(2);
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/livekit/session/sighttalk-test/agent/start',
        expect.objectContaining({ method: 'POST' }),
      ),
    );
  });

  it('renders realtime captions and sends interrupt only', async () => {
    const { stream } = createStream();
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue(stream),
      },
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: '开始' }));
    const room = await latestRoom();
    const audioElement = document.createElement('audio');
    const pause = vi.spyOn(audioElement, 'pause').mockImplementation(() => undefined);
    const play = vi.spyOn(audioElement, 'play').mockResolvedValue(undefined);
    room.emitTrackSubscribed({
      kind: 'audio',
      attach: () => audioElement,
    });

    act(() => {
      room.emitData({
        type: 'transcript.done',
        session_id: 'sighttalk-test',
        timestamp: new Date().toISOString(),
        speaker: 'user',
        text: '桌上有什么？',
        message_id: 'user-1',
      });
      room.emitData({
        type: 'transcript.done',
        session_id: 'sighttalk-test',
        timestamp: new Date().toISOString(),
        speaker: 'assistant',
        text: '我看到桌面中央有一个杯子。',
        message_id: 'assistant-1',
      });
    });

    expect(screen.queryByText('桌上有什么？')).not.toBeInTheDocument();
    expect(screen.getAllByText('我看到桌面中央有一个杯子。').length).toBeGreaterThan(0);

    await user.click(screen.getByRole('button', { name: '打断' }));

    expect(room.localParticipant.publishData).toHaveBeenCalledTimes(1);
    expect(pause).toHaveBeenCalled();
    expect(audioElement.muted).toBe(true);

    act(() => {
      room.emitData({
        type: 'transcript.delta',
        session_id: 'sighttalk-test',
        timestamp: new Date().toISOString(),
        speaker: 'assistant',
        text: '新的回答',
        message_id: 'assistant-2',
      });
    });

    expect(audioElement.muted).toBe(false);
    expect(play).toHaveBeenCalled();
  });

  it('stops session and releases local tracks', async () => {
    const { stream, audio, video } = createStream();
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue(stream),
      },
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: '开始' }));
    await user.click(await screen.findByRole('button', { name: '结束' }));

    await waitFor(() => expect(audio.stop).toHaveBeenCalled());
    expect(video.stop).toHaveBeenCalled();
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/livekit/session/sighttalk-test/end',
      expect.objectContaining({ method: 'POST' }),
    );
  });
});
