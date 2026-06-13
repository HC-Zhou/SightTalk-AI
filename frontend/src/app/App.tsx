import { Phone, PhoneOff, Sparkles, Zap } from 'lucide-react';
import { useEffect, useMemo, useRef } from 'react';

import { useSightTalkSession, statusLabel } from '../features/session/useSightTalkSession';
import type { SessionStatus } from '../features/session/types';

const cn = (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' ');

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
const dockButtonGlow = 'motion-safe:enabled:animate-dock-glow';
const captionBase =
  'mx-auto max-w-[min(560px,52vw)] rounded-2xl bg-white/72 px-4 py-2 text-[0.92rem] font-semibold leading-[1.35] text-slate-950 shadow-[0_12px_28px_rgba(15,23,42,0.18)] backdrop-blur-md';

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
  const session = useSightTalkSession();
  const canStart = session.status === 'idle' || session.status === 'ended' || session.status === 'error';
  const isActive = !canStart && session.status !== 'requesting-permission';
  const latestAssistantMessage = useMemo(
    () => [...session.messages].reverse().find((message) => message.speaker === 'assistant'),
    [session.messages],
  );
  const assistantCaption = latestAssistantMessage?.text ?? '点击开始后直接说话，我会结合摄像头画面回答。';
  const shouldScrollAssistantCaption = assistantCaption.length > 42;
  const assistantCaptionDuration = `${Math.min(Math.max(assistantCaption.length * 0.16, 7), 18)}s`;

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.srcObject = session.localPreviewStream ?? null;
    }
  }, [session.localPreviewStream]);

  return (
    <main className="fixed inset-0 min-h-[720px] min-w-[1024px] overflow-hidden bg-gradient-to-br from-slate-50 via-sky-50 to-slate-100 font-sans text-slate-900 antialiased">
      <video
        className="absolute inset-0 h-full w-full bg-slate-100 object-cover"
        ref={videoRef}
        autoPlay
        muted
        playsInline
      />

      {!session.localPreviewStream && (
        <section
          className="absolute inset-0 z-30 grid place-content-center justify-items-center bg-slate-50/90"
          aria-label="Start conversation"
        >
          <div className="flex items-center gap-[18px] text-left">
            <span className="grid h-[58px] w-[58px] place-items-center rounded-full bg-gradient-to-br from-sky-500 to-cyan-400 text-white shadow-[0_14px_28px_rgba(14,116,190,0.22)]">
              <Sparkles size={22} />
            </span>
            <div>
              <p className="m-0 mb-1 text-[0.82rem] font-extrabold uppercase text-slate-500">
                SightTalk AI
              </p>
              <h1 className="m-0 text-[3.4rem] leading-none text-slate-950">视频对话助手</h1>
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

      {session.localPreviewStream && (
        <section
          className="absolute left-1/2 top-[58%] z-40 w-[min(620px,58vw)] -translate-x-1/2 text-center"
          aria-live="polite"
        >
          <h2 className={cn(captionBase, 'm-0')}>
            <span className="block max-h-[2.5rem] overflow-hidden">
              <span
                className={cn('block', shouldScrollAssistantCaption && 'motion-safe:animate-caption-scroll')}
                key={latestAssistantMessage?.id ?? 'assistant-empty'}
                style={shouldScrollAssistantCaption ? { animationDuration: assistantCaptionDuration } : undefined}
              >
                {assistantCaption}
              </span>
            </span>
          </h2>
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
