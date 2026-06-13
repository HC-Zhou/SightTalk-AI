import { Mic, Phone, PhoneOff, Radio, Sparkles, Zap } from 'lucide-react';
import { useEffect, useMemo, useRef } from 'react';

import { useSightTalkSession, statusLabel } from '../features/session/useSightTalkSession';

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
    <main className="app-shell">
      <video className="camera-canvas" ref={videoRef} autoPlay muted playsInline />
      <div className="ambient-layer" />

      {!session.localPreviewStream && (
        <section className="preflight" aria-label="Start conversation">
          <div className="brand-lockup">
            <span className="brand-mark">
              <Sparkles size={22} />
            </span>
            <div>
              <p>SightTalk AI</p>
              <h1>视频对话助手</h1>
            </div>
          </div>
          <button className="start-button hero-start" onClick={session.start} type="button">
            <Phone size={20} />
            开始对话
          </button>
        </section>
      )}

      <header className="session-topbar">
        <div className="room-title">
          <span className={`live-dot status-${session.status}`} />
          <div>
            <p>SightTalk AI</p>
            <strong>{statusLabel(session.status)}</strong>
          </div>
        </div>
        <div className="listening-meter" aria-label="Automatic listening state">
          <Mic size={17} />
          <span>{isActive ? '自动监听中' : '等待开始'}</span>
        </div>
      </header>

      <section className="subtitle-stage" aria-live="polite">
        {latestUserMessage && (
          <p className="user-caption">
            <span>你</span>
            {latestUserMessage.text}
          </p>
        )}
        <h2>{latestAssistantMessage?.text ?? '点击开始后直接说话，我会结合摄像头画面回答。'}</h2>
      </section>

      <aside className="transcript-rail" aria-label="Realtime transcript">
        <div className="rail-heading">
          <Radio size={16} />
          <span>实时字幕</span>
        </div>
        <div className="rail-messages">
          {session.messages.length === 0 ? (
            <p className="rail-empty">语音识别、视觉理解和回答会自动显示在这里。</p>
          ) : (
            session.messages.slice(-5).map((message) => (
              <article className={`rail-message ${message.speaker}`} key={message.id}>
                <span>{message.speaker === 'user' ? '你' : 'AI'}</span>
                <p>{message.text}</p>
              </article>
            ))
          )}
        </div>
      </aside>

      {session.error && (
        <div className="error-banner" role="alert">
          <strong>{session.error.code}</strong>
          <span>{session.error.message}</span>
        </div>
      )}

      <footer className="control-dock" aria-label="Conversation controls">
        <div className="dock-status">
          <span>Frames {session.cost?.imageFramesSent ?? 0}</span>
          <span>Audio {session.cost?.audioSeconds.toFixed(1) ?? '0.0'}s</span>
          <span>{session.assistantAudioActive ? '语音播报已连接' : '等待语音播报'}</span>
        </div>
        <div className="dock-actions">
          {canStart ? (
            <button className="start-button" onClick={session.start} type="button">
              <Phone size={20} />
              开始
            </button>
          ) : (
            <>
              <button className="stop-button" onClick={session.stop} type="button">
                <PhoneOff size={20} />
                结束
              </button>
              <button className="interrupt-button" disabled={!isActive} onClick={session.interrupt} type="button">
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
