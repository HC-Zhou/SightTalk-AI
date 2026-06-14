import {
  Clock,
  LogOut,
  MessageSquareText,
  Phone,
  PhoneOff,
  Sparkles,
  UserRound,
  X,
  Zap,
} from 'lucide-react';
import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';

import { getCurrentUser, loginUser, registerUser } from '../features/auth/api';
import type { AuthCredentials, AuthResponse, AuthUser } from '../features/auth/types';
import { listConversations, saveConversation } from '../features/conversations/api';
import type { ConversationArchive } from '../features/conversations/types';
import { useSightTalkSession, statusLabel } from '../features/session/useSightTalkSession';
import type { ConversationMessage, SessionStatus } from '../features/session/types';

const cn = (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' ');
const AUTH_TOKEN_STORAGE_KEY = 'sighttalk.auth.token';
const mountainBackgroundStyle = {
  backgroundImage: "url('/snow-mountains.jpg')",
  backgroundPosition: 'center',
  backgroundSize: 'cover',
};

const surface =
  'border border-transparent bg-white/10 shadow-[0_12px_32px_rgba(30,45,70,0.08)] backdrop-blur-sm';
const pillSurface = cn(surface, 'rounded-full');
const buttonBase =
  'inline-flex h-[54px] min-w-[116px] cursor-pointer items-center justify-center gap-2.5 rounded-full border border-transparent px-5 font-black transition duration-150 ease-out backdrop-blur-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-45';
const primaryButton = cn(
  buttonBase,
  'bg-emerald-300/48 text-emerald-950 shadow-[inset_0_1px_0_rgba(255,255,255,0.44),0_14px_30px_rgba(5,150,105,0.2),0_0_24px_rgba(52,211,153,0.24)] hover:-translate-y-0.5 hover:bg-emerald-300/62 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.58),0_18px_38px_rgba(5,150,105,0.24),0_0_34px_rgba(52,211,153,0.34)] focus-visible:outline-emerald-400',
);
const secondaryButton = cn(
  buttonBase,
  'bg-white/48 text-slate-950 shadow-[inset_0_1px_0_rgba(255,255,255,0.44),0_12px_26px_rgba(30,45,70,0.12),0_0_20px_rgba(255,255,255,0.26)] hover:-translate-y-0.5 hover:bg-white/62 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.58),0_18px_36px_rgba(30,45,70,0.16),0_0_30px_rgba(255,255,255,0.38)] focus-visible:outline-slate-400',
);
const dangerButton = cn(
  buttonBase,
  'bg-rose-300/42 text-rose-950 shadow-[inset_0_1px_0_rgba(255,255,255,0.42),0_14px_30px_rgba(190,18,60,0.18),0_0_24px_rgba(251,113,133,0.24)] hover:-translate-y-0.5 hover:bg-rose-300/56 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.56),0_18px_38px_rgba(190,18,60,0.22),0_0_34px_rgba(251,113,133,0.32)] focus-visible:outline-rose-400',
);
const logoutButton = cn(
  buttonBase,
  'bg-red-500/74 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.18),0_12px_28px_rgba(185,28,28,0.26),0_0_22px_rgba(248,113,113,0.24)] hover:-translate-y-0.5 hover:bg-red-500/88 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.24),0_16px_34px_rgba(185,28,28,0.32),0_0_30px_rgba(248,113,113,0.34)] focus-visible:outline-red-300',
);
const dockButtonGlow = 'motion-safe:enabled:animate-dock-glow';

const statusDotClasses: Record<SessionStatus, string> = {
  idle: 'bg-slate-400',
  'requesting-permission': 'bg-sky-400 shadow-[0_0_0_8px_rgba(56,189,248,0.16)]',
  connecting: 'bg-sky-500 shadow-[0_0_0_8px_rgba(14,165,233,0.16)]',
  listening: 'bg-emerald-500 shadow-[0_0_0_8px_rgba(16,185,129,0.16)]',
  thinking: 'bg-amber-500 shadow-[0_0_0_8px_rgba(245,158,11,0.16)]',
  speaking: 'bg-emerald-500 shadow-[0_0_0_8px_rgba(16,185,129,0.16)]',
  interrupted: 'bg-emerald-500 shadow-[0_0_0_8px_rgba(16,185,129,0.16)]',
  error: 'bg-rose-500 shadow-[0_0_0_8px_rgba(244,63,94,0.16)]',
  ended: 'bg-slate-400',
};

export function App() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const savedSessionIdsRef = useRef<Set<string>>(new Set());
  const [authToken, setAuthToken] = useState(() => localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) ?? '');
  const [authUser, setAuthUser] = useState<AuthUser | undefined>(undefined);
  const [authLoading, setAuthLoading] = useState(() => Boolean(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)));
  const [conversationHistory, setConversationHistory] = useState<ConversationArchive[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<string | undefined>(undefined);
  const session = useSightTalkSession(authToken || undefined);
  const canStart = session.status === 'idle' || session.status === 'ended' || session.status === 'error';
  const isActive = !canStart && session.status !== 'requesting-permission';
  const selectedConversation = conversationHistory.find(
    (conversation) => conversation.id === selectedConversationId,
  );

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.srcObject = session.localPreviewStream ?? null;
    }
  }, [session.localPreviewStream]);

  useEffect(() => {
    if (!authToken) {
      setAuthUser(undefined);
      setAuthLoading(false);
      setConversationHistory([]);
      setSelectedConversationId(undefined);
      savedSessionIdsRef.current = new Set();
      return;
    }
    let cancelled = false;
    setAuthLoading(true);
    void getCurrentUser(authToken)
      .then((user) => {
        if (!cancelled) {
          setAuthUser(user);
          setAuthLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
          setAuthToken('');
          setAuthUser(undefined);
          setAuthLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [authToken]);

  useEffect(() => {
    if (!authUser || !authToken) {
      setConversationHistory([]);
      setSelectedConversationId(undefined);
      savedSessionIdsRef.current = new Set();
      return;
    }
    let cancelled = false;
    void listConversations(authToken)
      .then((history) => {
        if (cancelled) {
          return;
        }
        savedSessionIdsRef.current = new Set(history.map((conversation) => conversation.id));
        setConversationHistory(history);
        setSelectedConversationId((current) =>
          current && history.some((conversation) => conversation.id === current)
            ? current
            : history[0]?.id,
        );
      })
      .catch(() => {
        if (!cancelled) {
          savedSessionIdsRef.current = new Set();
          setConversationHistory([]);
          setSelectedConversationId(undefined);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [authToken, authUser]);

  const saveFinishedConversation = useCallback(() => {
    if (!authToken || !authUser || !session.session || savedSessionIdsRef.current.has(session.session.room_name)) {
      return;
    }
    const archive = createConversationArchive(session.session.room_name, session.messages);
    if (!archive) {
      return;
    }
    savedSessionIdsRef.current.add(archive.id);
    setConversationHistory((current) => {
      const next = [archive, ...current.filter((conversation) => conversation.id !== archive.id)];
      return next;
    });
    setSelectedConversationId(archive.id);
    void saveConversation(
      {
        session_id: archive.id,
        messages: archive.messages,
      },
      authToken,
    )
      .then((savedArchive) => {
        setConversationHistory((current) => [
          savedArchive,
          ...current.filter((conversation) => conversation.id !== savedArchive.id),
        ]);
        setSelectedConversationId(savedArchive.id);
      })
      .catch(() => {
        // The transcript remains visible locally for this page even if persistence fails.
      });
  }, [authToken, authUser, session.messages, session.session]);

  useEffect(() => {
    if (session.status === 'ended') {
      saveFinishedConversation();
    }
  }, [saveFinishedConversation, session.status]);

  const handleAuthenticated = useCallback((response: AuthResponse) => {
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, response.access_token);
    setAuthToken(response.access_token);
    setAuthUser(response.user);
    setAuthLoading(false);
  }, []);

  const handleLogout = useCallback(async () => {
    await session.stop();
    saveFinishedConversation();
    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    setAuthToken('');
    setAuthUser(undefined);
    setAuthLoading(false);
  }, [saveFinishedConversation, session]);

  const handleStop = useCallback(async () => {
    await session.stop();
    saveFinishedConversation();
  }, [saveFinishedConversation, session]);

  if (!authToken || !authUser) {
    return (
      <AuthScreen
        checking={authLoading}
        onAuthenticated={handleAuthenticated}
      />
    );
  }

  return (
    <main
      className="fixed inset-0 min-h-[720px] min-w-[1024px] overflow-hidden bg-slate-950 bg-cover bg-center font-sans text-slate-900 antialiased"
      style={mountainBackgroundStyle}
    >
      <div className="absolute inset-0 bg-slate-950/20" />
      {session.localPreviewStream && (
        <video
          className="absolute inset-0 h-full w-full object-cover"
          ref={videoRef}
          autoPlay
          muted
          playsInline
        />
      )}

      {!session.localPreviewStream && (
        <ConversationSidebar
          conversations={conversationHistory}
          selectedConversationId={selectedConversationId}
          onSelect={setSelectedConversationId}
        />
      )}

      {!session.localPreviewStream && (
        <section
          className={cn(
            'absolute inset-0 z-30 grid place-content-center justify-items-center bg-slate-950/25',
            'pl-[320px]',
          )}
          aria-label="Start conversation"
        >
          <div className="flex items-center gap-[18px] text-left">
            <span className="grid h-[58px] w-[58px] place-items-center rounded-full bg-gradient-to-br from-sky-500 to-cyan-400 text-white shadow-[0_14px_28px_rgba(14,116,190,0.22)]">
              <Sparkles size={22} />
            </span>
            <div>
              <p className="m-0 mb-1 text-[0.82rem] font-extrabold uppercase text-white/72">
                SightTalk AI
              </p>
              <h1 className="m-0 text-[3.4rem] leading-none text-white">视频对话助手</h1>
            </div>
          </div>
        </section>
      )}

      {selectedConversation && !session.localPreviewStream && (
        <ConversationDetail
          conversation={selectedConversation}
          onClose={() => setSelectedConversationId(undefined)}
        />
      )}

      <header
        className={cn(
          'absolute top-7 z-40 transition-[left] duration-150',
          session.localPreviewStream ? 'left-8' : 'left-[348px]',
        )}
      >
        <div className={cn(pillSurface, 'flex min-h-[58px] min-w-[220px] items-center gap-[13px] px-[18px]')}>
          <span
            className={cn(
              'h-3 w-3 rounded-full shadow-[inset_0_0_0_1px_rgba(255,255,255,0.42)]',
              statusDotClasses[session.status],
            )}
          />
          <div>
            <p className="m-0 mb-1 text-[0.82rem] font-extrabold uppercase text-slate-500">
              SightTalk AI
            </p>
            <strong className="block text-[1.05rem] text-slate-950">{statusLabel(session.status)}</strong>
          </div>
        </div>
      </header>

      <aside className="absolute right-8 top-7 z-40 flex items-center gap-2">
        <div className={cn(pillSurface, 'flex min-h-[48px] items-center gap-2.5 px-4 text-sm font-bold text-slate-800')}>
          <UserRound size={17} />
          <span>{authUser.email}</span>
        </div>
        <button
          className={cn(logoutButton, 'h-[48px] min-w-0 px-4')}
          onClick={handleLogout}
          type="button"
        >
          <LogOut size={18} />
          登出
        </button>
      </aside>

      {session.error && (
        <div
          className="absolute bottom-[114px] left-1/2 z-50 flex w-[min(680px,calc(100vw-64px))] -translate-x-1/2 items-center justify-center gap-3 rounded-3xl border border-rose-200 bg-rose-50 px-4 py-[13px] text-rose-800 shadow-[0_18px_45px_rgba(190,18,60,0.1)]"
          role="alert"
        >
          <strong>{session.error.code}</strong>
          <span>{session.error.message}</span>
        </div>
      )}

      <footer
        className="pointer-events-none absolute bottom-7 left-0 right-0 z-40 flex min-h-[72px] items-center justify-center"
        aria-label="Conversation controls"
      >
        <div className="pointer-events-auto inline-flex items-center gap-3.5">
          {canStart ? (
            <button className={cn(primaryButton, dockButtonGlow)} onClick={session.start} type="button">
              <Phone size={20} />
              开始
            </button>
          ) : (
            <>
              <button className={cn(secondaryButton, dockButtonGlow)} onClick={handleStop} type="button">
                <PhoneOff size={20} />
                结束
              </button>
              <button className={cn(dangerButton, dockButtonGlow)} disabled={!isActive} onClick={session.interrupt} type="button">
                <Zap size={20} />
                打断
              </button>
            </>
          )}
        </div>
      </footer>
    </main>
  );
}

interface ConversationSidebarProps {
  conversations: ConversationArchive[];
  selectedConversationId?: string;
  onSelect: (conversationId: string) => void;
}

function ConversationSidebar({
  conversations,
  selectedConversationId,
  onSelect,
}: ConversationSidebarProps) {
  return (
    <aside
      aria-label="历史对话"
      className="absolute bottom-6 left-6 top-6 z-50 flex w-[300px] flex-col overflow-hidden rounded-[26px] border border-white/16 bg-slate-950/58 p-4 text-white shadow-[0_24px_60px_rgba(2,6,23,0.26)] backdrop-blur-xl"
    >
      <div className="mb-4 flex min-h-[42px] items-center gap-3 px-1">
        <span className="grid h-10 w-10 place-items-center rounded-2xl bg-cyan-300 text-slate-950 shadow-[0_12px_26px_rgba(34,211,238,0.22)]">
          <MessageSquareText size={19} />
        </span>
        <div>
          <p className="m-0 text-[0.76rem] font-extrabold uppercase text-cyan-100/70">
            Conversations
          </p>
          <h2 className="m-0 text-[1.05rem] leading-tight">历史对话</h2>
        </div>
      </div>

      {conversations.length === 0 ? (
        <div className="grid flex-1 place-items-center rounded-[18px] border border-dashed border-white/14 px-5 text-center text-sm font-bold leading-6 text-white/58">
          暂无记录
        </div>
      ) : (
        <nav className="-mx-1 flex flex-1 flex-col gap-1 overflow-y-auto pr-1" aria-label="历史对话列表">
          {conversations.map((conversation) => {
            const selected = conversation.id === selectedConversationId;
            return (
              <button
                aria-pressed={selected}
                className={cn(
                  'grid min-h-[76px] cursor-pointer grid-cols-[auto_1fr] gap-3 rounded-[18px] border px-3 py-3 text-left transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-200',
                  selected
                    ? 'border-cyan-200/42 bg-cyan-100/18 text-white shadow-[0_12px_30px_rgba(14,165,233,0.16)]'
                    : 'border-transparent bg-white/0 text-white/78 hover:bg-white/10',
                )}
                key={conversation.id}
                onClick={() => onSelect(conversation.id)}
                type="button"
              >
                <span
                  className={cn(
                    'mt-0.5 grid h-9 w-9 place-items-center rounded-2xl',
                    selected ? 'bg-cyan-300 text-slate-950' : 'bg-white/10 text-cyan-100',
                  )}
                >
                  <MessageSquareText size={17} />
                </span>
                <span className="min-w-0">
                  <span className="block overflow-hidden text-ellipsis whitespace-nowrap text-sm font-extrabold">
                    {conversation.title}
                  </span>
                  <span className="mt-2 flex items-center gap-1.5 text-[0.75rem] font-bold text-white/52">
                    <Clock size={13} />
                    {formatConversationDate(conversation.endedAt)}
                  </span>
                </span>
              </button>
            );
          })}
        </nav>
      )}
    </aside>
  );
}

interface ConversationDetailProps {
  conversation: ConversationArchive;
  onClose: () => void;
}

function ConversationDetail({ conversation, onClose }: ConversationDetailProps) {
  return (
    <section
      aria-label="对话记录"
      className="absolute bottom-[118px] left-[356px] right-8 top-[112px] z-40 flex min-h-[360px] flex-col overflow-hidden rounded-[28px] border border-white/18 bg-slate-950/62 text-white shadow-[0_28px_70px_rgba(2,6,23,0.28)] backdrop-blur-xl"
    >
      <header className="flex min-h-[78px] items-center justify-between gap-4 border-b border-white/10 px-6">
        <div className="min-w-0">
          <p className="m-0 mb-1 text-[0.78rem] font-extrabold uppercase text-cyan-100/64">
            Transcript
          </p>
          <h2 className="m-0 overflow-hidden text-ellipsis whitespace-nowrap text-[1.35rem] leading-tight">
            {conversation.title}
          </h2>
        </div>
        <button
          aria-label="关闭记录"
          className="grid h-11 w-11 shrink-0 cursor-pointer place-items-center rounded-full border border-white/12 bg-white/10 text-white transition hover:bg-white/18 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-200"
          onClick={onClose}
          title="关闭记录"
          type="button"
        >
          <X size={20} />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="grid gap-3">
          {conversation.messages.map((message) => (
            <article
              className={cn(
                'rounded-[18px] border px-4 py-3',
                message.speaker === 'user'
                  ? 'border-cyan-200/20 bg-cyan-50/10'
                  : 'border-white/10 bg-white/10',
              )}
              key={message.id}
            >
              <p className="m-0 mb-2 text-[0.76rem] font-extrabold uppercase text-white/48">
                {message.speaker === 'user' ? '我' : '助手'}
              </p>
              <p className="m-0 whitespace-pre-wrap text-[0.98rem] font-semibold leading-7 text-white/88">
                {message.text}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

interface AuthScreenProps {
  checking: boolean;
  onAuthenticated: (response: AuthResponse) => void;
}

function AuthScreen({ checking, onAuthenticated }: AuthScreenProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [credentials, setCredentials] = useState<AuthCredentials>({
    email: '',
    password: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const isRegister = mode === 'register';

  const submit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setSubmitting(true);
      setError(undefined);
      try {
        const response = isRegister
          ? await registerUser(credentials)
          : await loginUser(credentials);
        onAuthenticated(response);
      } catch (authError) {
        setError(authError instanceof Error ? authError.message : 'Unable to authenticate');
      } finally {
        setSubmitting(false);
      }
    },
    [credentials, isRegister, onAuthenticated],
  );

  return (
    <main
      className="fixed inset-0 min-h-[640px] overflow-hidden bg-slate-950 bg-cover bg-center font-sans text-white antialiased"
      style={mountainBackgroundStyle}
    >
      <div className="absolute inset-0 bg-slate-950/40" />
      <section className="relative z-10 grid h-full place-items-center px-8">
        <div className="w-[min(420px,calc(100vw-48px))] rounded-[28px] border border-white/16 bg-white/12 p-7 shadow-[0_28px_80px_rgba(2,6,23,0.32)] backdrop-blur-xl">
          <div className="mb-7 flex items-center gap-4">
            <span className="grid h-12 w-12 place-items-center rounded-full bg-cyan-300 text-slate-950 shadow-[0_16px_34px_rgba(34,211,238,0.22)]">
              <Sparkles size={20} />
            </span>
            <div>
              <p className="m-0 text-[0.78rem] font-extrabold uppercase text-cyan-100/80">
                SightTalk AI
              </p>
              <h1 className="m-0 text-[2.35rem] leading-none">登录后开始</h1>
            </div>
          </div>

          <form className="grid gap-4" onSubmit={submit}>
            <label className="grid gap-2 text-sm font-bold text-cyan-50/86">
              邮箱
              <input
                className="h-12 rounded-2xl border border-white/12 bg-white/88 px-4 text-base font-semibold text-slate-950 outline-none transition focus:border-cyan-300 focus:bg-white"
                disabled={checking || submitting}
                onChange={(event) =>
                  setCredentials((current) => ({ ...current, email: event.target.value }))
                }
                type="email"
                value={credentials.email}
              />
            </label>
            <label className="grid gap-2 text-sm font-bold text-cyan-50/86">
              密码
              <input
                className="h-12 rounded-2xl border border-white/12 bg-white/88 px-4 text-base font-semibold text-slate-950 outline-none transition focus:border-cyan-300 focus:bg-white"
                disabled={checking || submitting}
                onChange={(event) =>
                  setCredentials((current) => ({ ...current, password: event.target.value }))
                }
                type="password"
                value={credentials.password}
              />
            </label>

            {error && (
              <p className="m-0 rounded-2xl border border-rose-200/42 bg-rose-100/92 px-4 py-3 text-sm font-bold text-rose-900">
                {error}
              </p>
            )}

            <button
              className={cn(primaryButton, 'mt-1 w-full bg-cyan-300/86 text-slate-950')}
              disabled={checking || submitting}
              type="submit"
            >
              {checking || submitting ? '处理中' : isRegister ? '注册账号' : '登录'}
            </button>
          </form>

          <button
            className="mt-5 w-full cursor-pointer border-0 bg-transparent text-sm font-extrabold text-cyan-50/86 underline-offset-4 hover:text-white hover:underline"
            disabled={checking || submitting}
            onClick={() => {
              setError(undefined);
              setMode(isRegister ? 'login' : 'register');
            }}
            type="button"
          >
            {isRegister ? '已有账号，去登录' : '没有账号，去注册'}
          </button>
        </div>
      </section>
    </main>
  );
}

function createConversationArchive(
  sessionId: string,
  messages: ConversationMessage[],
): ConversationArchive | null {
  const transcriptMessages = messages
    .map((message) => ({ ...message, text: message.text.trim() }))
    .filter((message) => message.text.length > 0);
  if (transcriptMessages.length === 0) {
    return null;
  }
  const endedAt = new Date().toISOString();
  return {
    id: sessionId,
    title: createConversationTitle(transcriptMessages),
    createdAt: endedAt,
    endedAt,
    messages: transcriptMessages,
  };
}

function createConversationTitle(messages: ConversationMessage[]) {
  const firstUserMessage = messages.find((message) => message.speaker === 'user') ?? messages[0];
  return truncateText(firstUserMessage.text, 28);
}

function truncateText(text: string, maxLength: number) {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 3)}...`;
}

function formatConversationDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}
