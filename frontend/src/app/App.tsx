import {
  Camera,
  CameraOff,
  Mic,
  MicOff,
  Phone,
  PhoneOff,
  Radio,
  Send,
  Zap,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { useSightTalkSession, statusLabel } from '../features/session/useSightTalkSession';
import type { MediaMode } from '../features/session/types';
import { IconButton } from '../shared/components/IconButton';

const modes: Array<{ value: MediaMode; label: string }> = [
  { value: 'economy', label: 'Economy' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'accurate', label: 'Accurate' },
];

interface SpeechRecognitionResultEvent extends Event {
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
}

interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionResultEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

interface WindowWithSpeechRecognition extends Window {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
}

export function App() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [draft, setDraft] = useState('');
  const [isRecognizing, setIsRecognizing] = useState(false);
  const session = useSightTalkSession();
  const canStart = session.status === 'idle' || session.status === 'ended' || session.status === 'error';
  const isActive = !canStart && session.status !== 'requesting-permission';

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.srcObject = session.localPreviewStream ?? null;
    }
  }, [session.localPreviewStream]);

  const captureFrame = useCallback(() => {
    const video = videoRef.current;
    if (!video || video.readyState < 2) {
      return undefined;
    }
    const canvas = document.createElement('canvas');
    canvas.width = Math.min(video.videoWidth || 640, 960);
    canvas.height = Math.round(canvas.width / ((video.videoWidth || 16) / (video.videoHeight || 9)));
    const context = canvas.getContext('2d');
    if (!context) {
      return undefined;
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.72);
  }, []);

  const sendPrompt = useCallback(
    async (prompt: string) => {
      const text = prompt.trim();
      if (!text || !isActive) {
        return;
      }
      setDraft('');
      await session.sendTurn(text, captureFrame());
    },
    [captureFrame, isActive, session],
  );

  const startSpeechRecognition = useCallback(() => {
    if (!isActive || isRecognizing) {
      return;
    }
    const speechWindow = window as WindowWithSpeechRecognition;
    const Recognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setDraft('当前浏览器不支持语音识别，请直接输入文字。');
      return;
    }
    const recognition = new Recognition();
    recognition.lang = 'zh-CN';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event) => {
      const transcript = event.results[0]?.[0]?.transcript ?? '';
      void sendPrompt(transcript);
    };
    recognition.onerror = (event) => {
      setDraft(`语音识别失败：${event.error}`);
    };
    recognition.onend = () => {
      setIsRecognizing(false);
    };
    setIsRecognizing(true);
    recognition.start();
  }, [isActive, isRecognizing, sendPrompt]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Realtime visual voice assistant</p>
          <h1>SightTalk AI</h1>
        </div>
        <div className={`status-pill status-${session.status}`}>
          <span />
          {statusLabel(session.status)}
        </div>
      </header>

      <section className="workspace">
        <div className="video-pane" aria-label="Camera preview">
          <video ref={videoRef} autoPlay muted playsInline />
          {!session.localPreviewStream && (
            <div className="video-placeholder">
              <Camera size={44} />
              <p>点击开始对话后，这里会显示摄像头画面。</p>
            </div>
          )}
          <div className="video-overlay">
            <span>{session.cameraEnabled ? '摄像头已开启' : '摄像头已关闭'}</span>
            <span>{session.micEnabled ? '麦克风已开启' : '麦克风已关闭'}</span>
          </div>
        </div>

        <aside className="conversation-pane" aria-label="Conversation">
          <div className="pane-header">
            <div>
              <p className="eyebrow">Transcript</p>
              <h2>Conversation</h2>
            </div>
            <Radio size={20} />
          </div>

          <div className="messages">
            {session.messages.length === 0 ? (
              <div className="empty-copy">
                <p>点击底部开始对话，允许摄像头和麦克风权限，然后用语音或文字提问。</p>
                {canStart && (
                  <button className="inline-start-button" onClick={session.start} type="button">
                    <Phone size={17} />
                    开始对话
                  </button>
                )}
              </div>
            ) : (
              session.messages.map((message) => (
                <article className={`message ${message.speaker}`} key={message.id}>
                  <span>{message.speaker}</span>
                  <p>{message.text}</p>
                </article>
              ))
            )}
          </div>

          <form
            className="turn-composer"
            onSubmit={(event) => {
              event.preventDefault();
              void sendPrompt(draft);
            }}
          >
            <textarea
              disabled={!isActive}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={isActive ? '也可以直接输入问题...' : '先点击开始对话'}
              value={draft}
            />
            <div className="composer-actions">
              <button disabled={!isActive || isRecognizing} onClick={startSpeechRecognition} type="button">
                <Mic size={17} />
                {isRecognizing ? '识别中' : '语音提问'}
              </button>
              <button disabled={!isActive || !draft.trim()} type="submit">
                <Send size={17} />
                发送
              </button>
            </div>
          </form>

          <div className="metrics">
            <div>
              <span>Audio</span>
              <strong>{session.cost?.audioSeconds.toFixed(1) ?? '0.0'}s</strong>
            </div>
            <div>
              <span>Frames</span>
              <strong>{session.cost?.imageFramesSent ?? 0}</strong>
            </div>
            <div>
              <span>Mode</span>
              <strong>{session.mediaMode}</strong>
            </div>
          </div>
        </aside>
      </section>

      {session.error && (
        <div className="error-banner" role="alert">
          <strong>{session.error.code}</strong>
          <span>{session.error.message}</span>
        </div>
      )}

      <footer className="control-bar">
        <div className="primary-controls">
          {canStart ? (
            <button className="start-button" onClick={session.start} type="button">
              <Phone size={18} />
              开始对话
            </button>
          ) : (
            <button className="stop-button" onClick={session.stop} type="button">
              <PhoneOff size={18} />
              结束
            </button>
          )}
          <IconButton
            active={session.micEnabled}
            disabled={!isActive}
            icon={session.micEnabled ? <Mic size={18} /> : <MicOff size={18} />}
            label={session.micEnabled ? 'Mute microphone' : 'Unmute microphone'}
            onClick={session.toggleMic}
          />
          <IconButton
            active={session.cameraEnabled}
            disabled={!isActive}
            icon={session.cameraEnabled ? <Camera size={18} /> : <CameraOff size={18} />}
            label={session.cameraEnabled ? 'Mute camera' : 'Unmute camera'}
            onClick={session.toggleCamera}
          />
          <IconButton
            disabled={!isActive}
            icon={<Zap size={18} />}
            label="Interrupt assistant"
            onClick={session.interrupt}
          />
        </div>

        <div className="mode-control" aria-label="Media mode">
          {modes.map((mode) => (
            <button
              className={session.mediaMode === mode.value ? 'selected' : ''}
              key={mode.value}
              onClick={() => session.setMediaMode(mode.value)}
              type="button"
            >
              {mode.label}
            </button>
          ))}
        </div>
      </footer>
    </main>
  );
}
