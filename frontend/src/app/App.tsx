import { LogOut, Phone, PhoneOff, Sparkles, UserRound, Zap } from 'lucide-react';
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { getCurrentUser, loginUser, registerUser } from '../features/auth/api';
import type { AuthCredentials, AuthResponse, AuthUser } from '../features/auth/types';
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
const captionBase =
  'mx-auto grid max-w-[min(680px,62vw)] gap-2 rounded-2xl bg-white/72 px-4 py-3 text-left text-[0.92rem] font-semibold leading-[1.35] text-slate-950 shadow-[0_12px_28px_rgba(15,23,42,0.18)] backdrop-blur-md';

const statusDotClasses: Record<SessionStatus, string> = {
  idle: 'bg-slate-400',
  'requesting-permission': 'bg-sky-400 shadow-[0_0_0_8px_rgba(56,189,248,0.16)]',
  connecting: 'bg-sky-500 shadow-[0_0_0_8px_rgba(14,165,233,0.16)]',
  listening: 'bg-emerald-500 shadow-[0_0_0_8px_rgba(16,185,129,0.16)]',
  thinking: 'bg-amber-500 shadow-[0_0_0_8px_rgba(245,158,11,0.16)]',
  speaking: 'bg-emerald-500 shadow-[0_0_0_8px_rgba(16,185,129,0.16)]',
  interrupted: 'bg-rose-500 shadow-[0_0_0_8px_rgba(244,63,94,0.16)]',
  error: 'bg-rose-500 shadow-[0_0_0_8px_rgba(244,63,94,0.16)]',
  ended: 'bg-slate-400',
};

export function App() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [authToken, setAuthToken] = useState(() => localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) ?? '');
  const [authUser, setAuthUser] = useState<AuthUser | undefined>(undefined);
  const [authLoading, setAuthLoading] = useState(() => Boolean(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)));
  const session = useSightTalkSession(authToken || undefined);
  const canStart = session.status === 'idle' || session.status === 'ended' || session.status === 'error';
  const isActive = !canStart && session.status !== 'requesting-permission';
  const captionMessages = useMemo(
    () => recentConversationTurns(session.messages, 2),
    [session.messages],
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

  const handleAuthenticated = useCallback((response: AuthResponse) => {
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, response.access_token);
    setAuthToken(response.access_token);
    setAuthUser(response.user);
    setAuthLoading(false);
  }, []);

  const handleLogout = useCallback(async () => {
    await session.stop();
    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    setAuthToken('');
    setAuthUser(undefined);
    setAuthLoading(false);
  }, [session]);

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
        <section
          className="absolute inset-0 z-30 grid place-content-center justify-items-center bg-slate-950/25"
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

      <header className="absolute left-8 top-7 z-40">
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

      {session.localPreviewStream && (
        <section
          className="absolute left-1/2 top-[58%] z-40 w-[min(720px,64vw)] -translate-x-1/2"
          aria-live="polite"
        >
          <div className={captionBase}>
            {captionMessages.length > 0 ? (
              captionMessages.map((message) => (
                <p
                  className={cn(
                    'm-0',
                    message.speaker === 'user' ? 'text-slate-700' : 'text-slate-950',
                  )}
                  key={message.id}
                >
                  <span className="mr-2 text-[0.76rem] font-black uppercase text-slate-500">
                    {message.speaker === 'user' ? '你' : 'AI'}
                  </span>
                  {message.text}
                </p>
              ))
            ) : (
              <p className="m-0 text-center text-slate-950">点击开始后直接说话，我会结合摄像头画面回答。</p>
            )}
          </div>
        </section>
      )}

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
              <button className={cn(secondaryButton, dockButtonGlow)} onClick={session.stop} type="button">
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

function recentConversationTurns(messages: ConversationMessage[], maxTurns: number) {
  if (messages.length === 0) {
    return [];
  }
  let userTurns = 0;
  let startIndex = messages.length - 1;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    startIndex = index;
    if (messages[index].speaker === 'user') {
      userTurns += 1;
      if (userTurns === maxTurns) {
        break;
      }
    }
  }
  if (userTurns === 0) {
    return messages.slice(-maxTurns);
  }
  return messages.slice(startIndex);
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
