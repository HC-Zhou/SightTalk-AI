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
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/api/v1/auth/login') || url.endsWith('/api/v1/auth/register')) {
      return new Response(
        JSON.stringify({
          user: {
            user_id: 'user-test',
            email: 'ada@example.com',
            created_at: '2026-06-13T12:00:00Z',
          },
          access_token: 'auth-token',
          token_type: 'bearer',
          expires_at: '2026-06-20T12:00:00Z',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      );
    }
    if (url.endsWith('/api/v1/auth/me')) {
      const headers = init?.headers as Record<string, string> | undefined;
      if (headers?.Authorization !== 'Bearer auth-token') {
        return new Response(JSON.stringify({ error: { message: 'Unauthorized' } }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response(
        JSON.stringify({
          user_id: 'user-test',
          email: 'ada@example.com',
          created_at: '2026-06-13T12:00:00Z',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      );
    }
    if (url.endsWith('/api/v1/conversations') && init?.method === 'GET') {
      return new Response(JSON.stringify({ conversations: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    if (url.endsWith('/api/v1/conversations') && init?.method === 'POST') {
      const body = JSON.parse(String(init.body)) as {
        session_id: string;
        messages: Array<{ text: string }>;
      };
      return new Response(
        JSON.stringify({
          id: body.session_id,
          title: body.messages[0]?.text ?? '对话记录',
          created_at: '2026-06-13T12:00:00Z',
          ended_at: '2026-06-13T12:01:00Z',
          messages: body.messages,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      );
    }
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

async function signIn(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('邮箱'), 'ada@example.com');
  await user.type(screen.getByLabelText('密码'), 'correct-horse');
  await user.click(screen.getByRole('button', { name: '登录' }));
  expect(await screen.findByRole('button', { name: '开始' })).toBeInTheDocument();
}

beforeEach(async () => {
  const module = (await import('livekit-client')) as unknown as LiveKitMockModule;
  module.__mockRooms.length = 0;
  localStorage.clear();
  vi.stubGlobal('fetch', mockSessionFetch());
});

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('App', () => {
  it('renders login/register interface before authentication', () => {
    render(<App />);

    expect(screen.getByRole('heading', { name: '登录后开始' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '开始' })).not.toBeInTheDocument();
  });

  it('logs in and renders automatic conversation entry without manual turn controls', async () => {
    const user = userEvent.setup();
    render(<App />);

    await signIn(user);

    expect(screen.getByRole('heading', { name: '视频对话助手' })).toBeInTheDocument();
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
    await signIn(user);

    await user.click(screen.getByRole('button', { name: '开始' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Permission denied');
    expect(fetch).not.toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/livekit/session',
      expect.objectContaining({ method: 'POST' }),
    );
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
    await signIn(user);

    await user.click(screen.getByRole('button', { name: '开始' }));

    expect(await screen.findByText('Listening')).toBeInTheDocument();
    expect(screen.queryByLabelText('历史对话')).not.toBeInTheDocument();
    const room = await latestRoom();
    expect(room.connect).toHaveBeenCalledWith('ws://localhost:7880', 'token');
    expect(room.localParticipant.publishTrack).toHaveBeenCalledTimes(2);
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/livekit/session',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer auth-token' }),
      }),
    );
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/livekit/session/sighttalk-test/agent/start',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({ Authorization: 'Bearer auth-token' }),
        }),
      ),
    );
  });

  it('hides the history sidebar during video and restores it after ending', async () => {
    const { stream } = createStream();
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue(stream),
      },
    });
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    expect(screen.getByLabelText('历史对话')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '开始' }));
    expect(await screen.findByText('Listening')).toBeInTheDocument();
    expect(screen.queryByLabelText('历史对话')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '结束' }));

    expect(await screen.findByLabelText('历史对话')).toBeInTheDocument();
  });

  it('hides realtime captions and sends interrupt only', async () => {
    const { stream } = createStream();
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue(stream),
      },
    });
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

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
        text: '第一轮问题',
        message_id: 'user-1',
      });
      room.emitData({
        type: 'transcript.done',
        session_id: 'sighttalk-test',
        timestamp: new Date().toISOString(),
        speaker: 'assistant',
        text: '第一轮回答',
        message_id: 'assistant-1',
      });
      room.emitData({
        type: 'transcript.done',
        session_id: 'sighttalk-test',
        timestamp: new Date().toISOString(),
        speaker: 'user',
        text: '第二轮问题',
        message_id: 'user-2',
      });
      room.emitData({
        type: 'transcript.done',
        session_id: 'sighttalk-test',
        timestamp: new Date().toISOString(),
        speaker: 'assistant',
        text: '第二轮回答',
        message_id: 'assistant-2',
      });
      room.emitData({
        type: 'transcript.done',
        session_id: 'sighttalk-test',
        timestamp: new Date().toISOString(),
        speaker: 'user',
        text: '第三轮问题',
        message_id: 'user-3',
      });
      room.emitData({
        type: 'transcript.done',
        session_id: 'sighttalk-test',
        timestamp: new Date().toISOString(),
        speaker: 'assistant',
        text: '第三轮回答',
        message_id: 'assistant-3',
      });
    });

    expect(screen.queryByText('第一轮问题')).not.toBeInTheDocument();
    expect(screen.queryByText('第一轮回答')).not.toBeInTheDocument();
    expect(screen.queryByText('第二轮问题')).not.toBeInTheDocument();
    expect(screen.queryByText('第二轮回答')).not.toBeInTheDocument();
    expect(screen.queryByText('第三轮问题')).not.toBeInTheDocument();
    expect(screen.queryByText('第三轮回答')).not.toBeInTheDocument();

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
        message_id: 'assistant-4',
      });
      room.emitData({
        type: 'transcript.delta',
        session_id: 'sighttalk-test',
        timestamp: new Date().toISOString(),
        speaker: 'assistant',
        text: '新的回答',
        message_id: 'assistant-4',
      });
    });

    expect(screen.queryByText('新的回答')).not.toBeInTheDocument();
    expect(screen.queryByText('新的回答新的回答')).not.toBeInTheDocument();
    expect(audioElement.muted).toBe(false);
    expect(play).toHaveBeenCalled();
  });

  it('keeps local media enabled for voice barge-in during assistant audio', async () => {
    const { stream, audio, video } = createStream();
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue(stream),
      },
    });
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    await user.click(screen.getByRole('button', { name: '开始' }));
    const room = await latestRoom();

    expect(audio.enabled).toBe(true);
    expect(video.enabled).toBe(true);

    act(() => {
      room.emitData({
        type: 'agent.status',
        session_id: 'sighttalk-test',
        timestamp: new Date().toISOString(),
        status: 'speaking',
      });
    });

    expect(audio.enabled).toBe(true);
    expect(video.enabled).toBe(true);

    act(() => {
      room.emitData({
        type: 'response.done',
        session_id: 'sighttalk-test',
        timestamp: new Date().toISOString(),
        message_id: 'assistant-1',
        audio_playback_complete: true,
      });
    });

    expect(audio.enabled).toBe(true);
    expect(video.enabled).toBe(true);

    act(() => {
      room.emitData({
        type: 'agent.status',
        session_id: 'sighttalk-test',
        timestamp: new Date().toISOString(),
        status: 'speaking',
      });
    });
    await user.click(screen.getByRole('button', { name: '打断' }));

    expect(audio.enabled).toBe(true);
    expect(video.enabled).toBe(true);
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
    await signIn(user);

    await user.click(screen.getByRole('button', { name: '开始' }));
    await user.click(await screen.findByRole('button', { name: '结束' }));

    await waitFor(() => expect(audio.stop).toHaveBeenCalled());
    expect(video.stop).toHaveBeenCalled();
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/livekit/session/sighttalk-test/end',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer auth-token' }),
      }),
    );
  });

  it('saves ended video transcripts in the history sidebar', async () => {
    const { stream } = createStream();
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue(stream),
      },
    });
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    await user.click(screen.getByRole('button', { name: '开始' }));
    const room = await latestRoom();

    act(() => {
      room.emitData({
        type: 'transcript.done',
        session_id: 'sighttalk-test',
        timestamp: new Date().toISOString(),
        speaker: 'user',
        text: '今天的天气怎么样',
        message_id: 'user-weather',
      });
      room.emitData({
        type: 'transcript.done',
        session_id: 'sighttalk-test',
        timestamp: new Date().toISOString(),
        speaker: 'assistant',
        text: '今天适合出门散步。',
        message_id: 'assistant-weather',
      });
    });

    expect(screen.queryByText('今天的天气怎么样')).not.toBeInTheDocument();

    await user.click(await screen.findByRole('button', { name: '结束' }));

    expect(await screen.findByRole('button', { name: /今天的天气怎么样/ })).toBeInTheDocument();
    expect(screen.getByLabelText('对话记录')).toHaveTextContent('今天适合出门散步。');
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/conversations',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer auth-token' }),
        body: expect.stringContaining('今天的天气怎么样'),
      }),
    );
    expect(localStorage.getItem('sighttalk.conversation-history.user-test')).toBeNull();

    await user.click(screen.getByRole('button', { name: '关闭记录' }));
    expect(screen.queryByLabelText('对话记录')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /今天的天气怎么样/ }));
    expect(screen.getByLabelText('对话记录')).toHaveTextContent('今天的天气怎么样');
  });

  it('loads authenticated conversation history into the sidebar', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/api/v1/auth/login')) {
        return new Response(
          JSON.stringify({
            user: {
              user_id: 'user-test',
              email: 'ada@example.com',
              created_at: '2026-06-13T12:00:00Z',
            },
            access_token: 'auth-token',
            token_type: 'bearer',
            expires_at: '2026-06-20T12:00:00Z',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }
      if (url.endsWith('/api/v1/conversations')) {
        return new Response(
          JSON.stringify({
            conversations: [
              {
                id: 'room-history',
                title: '历史里的问题',
                created_at: '2026-06-13T12:00:00Z',
                ended_at: '2026-06-13T12:01:00Z',
                messages: [
                  {
                    id: 'user-history',
                    speaker: 'user',
                    text: '历史里的问题',
                    final: true,
                  },
                ],
              },
            ],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }
      return mockSessionFetch()(input, init);
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await signIn(user);

    expect(await screen.findByRole('button', { name: /历史里的问题/ })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/conversations',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'Bearer auth-token' }),
      }),
    );
  });

  it('registers and logs out by clearing the stored token', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: '没有账号，去注册' }));
    await user.type(screen.getByLabelText('邮箱'), 'ada@example.com');
    await user.type(screen.getByLabelText('密码'), 'correct-horse');
    await user.click(screen.getByRole('button', { name: '注册账号' }));

    expect(await screen.findByRole('button', { name: '开始' })).toBeInTheDocument();
    expect(localStorage.getItem('sighttalk.auth.token')).toBe('auth-token');

    await user.click(screen.getByRole('button', { name: '登出' }));

    expect(localStorage.getItem('sighttalk.auth.token')).toBeNull();
    expect(await screen.findByRole('button', { name: '登录' })).toBeInTheDocument();
  });
});
