import { Mic, Phone, PhoneOff, Radio, Sparkles, Zap } from 'lucide-react';
import { useEffect, useMemo, useRef } from 'react';

import { useSightTalkSession, statusLabel } from '../features/session/useSightTalkSession';
import type { SessionStatus } from '../features/session/types';

const cn = (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' ');

const surface =
  'border border-slate-200/80 bg-white shadow-[0_18px_45px_rgba(30,45,70,0.12)]';
const pillSurface = cn(surface, 'rounded-full');
const panelSurface = cn(surface, 'rounded-[28px]');
const buttonBase =
  'inline-flex h-[54px] min-w-[116px] cursor-pointer items-center justify-center gap-2.5 rounded-full border px-5 font-black transition duration-150 ease-out focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-45';
const primaryButton = cn(
  buttonBase,
  'border-sky-300 bg-gradient-to-r from-sky-500 to-cyan-400 text-white shadow-[0_14px_30px_rgba(14,116,190,0.22)] hover:-translate-y-0.5 hover:shadow-[0_18px_36px_rgba(14,116,190,0.24)] focus-visible:outline-sky-400',
);
const secondaryButton = cn(
  buttonBase,
  'border-slate-200 bg-white text-slate-700 shadow-[0_12px_26px_rgba(30,45,70,0.1)] hover:-translate-y-0.5 hover:shadow-[0_18px_36px_rgba(30,45,70,0.15)] focus-visible:outline-slate-400',
);
const dangerButton = cn(
  buttonBase,
  'border-rose-300 bg-gradient-to-r from-rose-500 to-red-500 text-white shadow-[0_14px_30px_rgba(190,18,60,0.18)] hover:-translate-y-0.5 hover:shadow-[0_18px_36px_rgba(190,18,60,0.22)] focus-visible:outline-rose-400',
);

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
  const latestUserMessage = useMemo(
    () => [...session.messages].reverse().find((message) => message.speaker === 'user'),
    [session.messages],
  );
  const latestAssistantMessage = useMemo(
    () => [...session.messages].reverse().find((message) => message.speaker === 'assistant'),
    [session.messages],
  );

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
          className="absolute inset-0 z-30 grid place-content-center justify-items-center gap-[30px] bg-slate-50/90"
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
          <button className={cn(primaryButton, 'h-[62px] min-w-[172px] px-6')} onClick={session.start} type="button">
            <Phone size={20} />
            开始对话
          </button>
        </section>
      )}

      <header className="absolute left-8 right-8 top-7 z-40 flex items-center justify-between gap-5">
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
        <div
          className={cn(
            pillSurface,
            'inline-flex h-[46px] items-center gap-2.5 px-4 font-extrabold text-slate-600',
          )}
          aria-label="Automatic listening state"
        >
          <Mic size={17} />
          <span>{isActive ? '自动监听中' : '等待开始'}</span>
        </div>
      </header>

      <section
        className="absolute bottom-[154px] left-1/2 z-40 w-[min(620px,58vw)] -translate-x-1/2 text-center"
        aria-live="polite"
      >
        {latestUserMessage && (
          <p className="mx-auto mb-2.5 w-fit max-w-[84%] rounded-full border border-slate-200 bg-white px-3.5 py-2 text-[0.9rem] leading-[1.42] text-slate-600 shadow-[0_10px_28px_rgba(30,45,70,0.09)]">
            <span className="mr-2.5 font-black text-sky-600">你</span>
            {latestUserMessage.text}
          </p>
        )}
        <h2 className={cn(panelSurface, 'm-0 px-[18px] py-3 text-[clamp(1rem,1.6vw,1.45rem)] font-bold leading-[1.34] text-slate-800')}>
          {latestAssistantMessage?.text ?? '点击开始后直接说话，我会结合摄像头画面回答。'}
        </h2>
      </section>

      <aside
        className={cn(
          panelSurface,
          'absolute right-8 top-[108px] z-40 max-h-[calc(100dvh-240px)] w-[292px] overflow-hidden p-4',
        )}
        aria-label="Realtime transcript"
      >
        <div className="flex items-center gap-2 text-[0.84rem] font-black text-slate-500">
          <Radio size={16} />
          <span>实时字幕</span>
        </div>
        <div className="mt-4 flex max-h-[calc(100dvh-306px)] flex-col gap-[13px] overflow-auto">
          {session.messages.length === 0 ? (
            <p className="m-0 leading-normal text-slate-600">
              语音识别、视觉理解和回答会自动显示在这里。
            </p>
          ) : (
            session.messages.slice(-5).map((message) => (
              <article
                className={cn(
                  'border-l-2 py-0 pl-3',
                  message.speaker === 'assistant' ? 'border-sky-500/70' : 'border-slate-300',
                )}
                key={message.id}
              >
                <span className="mb-1 block text-[0.72rem] font-black text-slate-400">
                  {message.speaker === 'user' ? '你' : 'AI'}
                </span>
                <p className="m-0 leading-normal text-slate-600">{message.text}</p>
              </article>
            ))
          )}
        </div>
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
        className="pointer-events-none absolute bottom-7 left-8 right-8 z-40 grid min-h-[72px] grid-cols-[1fr_auto_1fr] items-center"
        aria-label="Conversation controls"
      >
        <div
          className={cn(
            pillSurface,
            'pointer-events-auto inline-flex min-h-11 w-fit items-center gap-3.5 px-4 text-[0.82rem] font-extrabold text-slate-500',
          )}
        >
          <span>Frames {session.cost?.imageFramesSent ?? 0}</span>
          <span>Audio {session.cost?.audioSeconds.toFixed(1) ?? '0.0'}s</span>
          <span>{session.assistantAudioActive ? '语音播报已连接' : '等待语音播报'}</span>
        </div>
        <div className="pointer-events-auto col-start-2 inline-flex items-center gap-3.5">
          {canStart ? (
            <button className={primaryButton} onClick={session.start} type="button">
              <Phone size={20} />
              开始
            </button>
          ) : (
            <>
              <button className={secondaryButton} onClick={session.stop} type="button">
                <PhoneOff size={20} />
                结束
              </button>
              <button className={dangerButton} disabled={!isActive} onClick={session.interrupt} type="button">
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
