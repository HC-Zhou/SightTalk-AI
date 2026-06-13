import { Mic, PhoneOff, Send, Sparkles, Upload, Video, Wifi, WifiOff } from "lucide-react";
import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useCameraSampler } from "./hooks/useCameraSampler";
import { useMicrophoneRecorder } from "./hooks/useMicrophoneRecorder";
import { createApiConfig, resolveApiAssetUrl } from "./shared/apiConfig";
import { initialSessionState, sessionReducer } from "./shared/sessionReducer";
import { type ClientStatus, VisionSessionClient } from "./shared/wsClient";

const SESSION_ID = "demo-session";

function formatConnectionStatus(
  transportStatus: ClientStatus | "idle",
  sessionStatus: string
): string {
  if (transportStatus === "idle") {
    return "等待连接";
  }
  if (transportStatus === "connecting") {
    return "连接中";
  }
  if (transportStatus === "open" && sessionStatus === "thinking") {
    return "思考中";
  }
  if (transportStatus === "open") {
    return "已连接";
  }
  if (transportStatus === "error") {
    return "连接异常";
  }
  return "已断开";
}

export default function App() {
  const [state, dispatch] = useReducer(sessionReducer, initialSessionState);
  const [transportStatus, setTransportStatus] = useState<ClientStatus | "idle">("idle");
  const clientRef = useRef<VisionSessionClient | null>(null);
  const camera = useCameraSampler(state.policy);
  const microphone = useMicrophoneRecorder();
  const apiConfig = useMemo(() => createApiConfig(), []);

  const isSessionOpen = transportStatus === "open";
  const isConnecting = transportStatus === "connecting";
  const connectionLabel = formatConnectionStatus(transportStatus, state.connectionStatus);
  const subtitleText =
    state.liveSubtitle?.text ||
    (state.liveSubtitle?.phase === "thinking"
      ? "正在思考"
      : isSessionOpen
        ? "正在聆听"
        : "等待连接");
  const subtitleSpeaker =
    state.liveSubtitle?.speaker === "user"
      ? "你"
      : state.liveSubtitle?.phase === "thinking"
        ? "AI"
        : "AI";
  const visibleMessages = state.messages.slice(Math.max(0, state.messages.length - 6));
  const errorMessage = state.errorMessage ?? camera.errorMessage ?? microphone.errorMessage;

  useEffect(() => {
    if (!state.ttsUrl) {
      return;
    }
    const audio = new Audio(resolveApiAssetUrl(state.ttsUrl, apiConfig));
    void audio.play().catch(() => {
      dispatch({
        type: "error",
        stage: "playback",
        message: "语音播放失败",
        retryable: true
      });
    });
  }, [apiConfig, state.ttsUrl]);

  const startSession = async () => {
    clientRef.current?.close();
    const client = new VisionSessionClient({
      sessionId: SESSION_ID,
      apiConfig,
      onEvent: dispatch,
      onStatus: setTransportStatus,
      onClientError: (error) => {
        dispatch({
          type: "error",
          stage: error.stage,
          message: error.reason ? `${error.message}: ${error.reason}` : error.message,
          retryable: true
        });
      }
    });
    client.connect();
    clientRef.current = client;

    await camera.start((frame) => {
      client.send({ type: "video.frame", ...frame });
    });
    await microphone.start((chunk) => {
      client.send({ type: "audio.chunk", ...chunk });
    });
  };

  const endUtterance = () => {
    const audioSeqEnd = microphone.markUtteranceEnd();
    clientRef.current?.send({ type: "utterance.end", audio_seq_end: audioSeqEnd });
  };

  const stopSession = () => {
    camera.stop();
    microphone.stop();
    clientRef.current?.close();
    clientRef.current = null;
    setTransportStatus("closed");
  };

  return (
    <main className="video-call-shell">
      <section className="video-call-stage" aria-label="视频对话">
        <div className="top-overlay">
          <div>
            <p className="product-label">SightTalk AI</p>
            <h1>SightTalk AI</h1>
          </div>
          <div className={`connection-pill status-${transportStatus}`}>
            {transportStatus === "error" || state.connectionStatus === "error" ? (
              <WifiOff aria-hidden="true" size={16} />
            ) : (
              <Wifi aria-hidden="true" size={16} />
            )}
            <span>{connectionLabel}</span>
          </div>
        </div>

        <div className={`video-surface ${camera.status === "active" ? "is-live" : ""}`}>
          <video
            ref={camera.videoRef}
            className="video-feed"
            playsInline
            muted
            aria-label="本地摄像头画面"
          />
          <div className="camera-standby" aria-hidden="true">
            <Sparkles size={32} />
            <span>{camera.status === "active" ? "画面采集中" : "视觉待机"}</span>
          </div>
        </div>

        <div className="subtitle-overlay" aria-live="polite">
          <span>{subtitleSpeaker}</span>
          <p>{subtitleText}</p>
        </div>

        <div className="call-controls" aria-label="通话控制">
          <button
            type="button"
            className="control-button"
            aria-label="开始通话"
            title="开始通话"
            onClick={startSession}
            disabled={isConnecting}
          >
            <Mic aria-hidden="true" size={34} />
          </button>
          <button
            type="button"
            className="control-button secondary"
            aria-label="提交发言"
            title="提交发言"
            onClick={endUtterance}
            disabled={!isSessionOpen}
          >
            <Send aria-hidden="true" size={30} />
          </button>
          <button
            type="button"
            className="control-button video-state"
            aria-label="画面采集"
            title="画面采集"
            disabled
          >
            <Video aria-hidden="true" size={32} />
          </button>
          <button
            type="button"
            className="control-button upload-state"
            aria-label="上传画面"
            title="上传画面"
            disabled
          >
            <Upload aria-hidden="true" size={30} />
          </button>
          <button
            type="button"
            className="control-button danger"
            aria-label="挂断"
            title="挂断"
            onClick={stopSession}
            disabled={transportStatus === "idle"}
          >
            <PhoneOff aria-hidden="true" size={34} />
          </button>
        </div>
      </section>

      <aside className="subtitle-rail" aria-label="实时字幕轨">
        <div className="rail-header">
          <div>
            <p className="rail-kicker">Live Caption</p>
            <h2>实时字幕</h2>
          </div>
          <span>{connectionLabel}</span>
        </div>

        <section className="live-caption-block" aria-label="当前字幕">
          <span>{subtitleSpeaker}</span>
          <p>{subtitleText}</p>
        </section>

        <section className="rail-section" aria-label="对话历史">
          <h3>最近对话</h3>
          {visibleMessages.length > 0 || state.assistantDraft ? (
            <div className="message-stack">
              {visibleMessages.map((message, index) => (
                <article className={`rail-message ${message.role}`} key={`${message.role}-${index}`}>
                  <span>{message.role === "user" ? "你" : "AI"}</span>
                  <p>{message.text}</p>
                </article>
              ))}
              {state.assistantDraft ? (
                <article className="rail-message assistant streaming">
                  <span>AI</span>
                  <p>{state.assistantDraft}</p>
                </article>
              ) : null}
            </div>
          ) : (
            <p className="empty-copy">等待第一轮对话</p>
          )}
        </section>

        <section className="rail-section" aria-label="采集状态">
          <h3>状态</h3>
          <dl className="status-list">
            <div>
              <dt>摄像头</dt>
              <dd>{camera.status}</dd>
            </div>
            <div>
              <dt>麦克风</dt>
              <dd>{microphone.status}</dd>
            </div>
            <div>
              <dt>策略</dt>
              <dd>{state.cost?.policy ?? "normal"}</dd>
            </div>
          </dl>
        </section>

        <section className="rail-section" aria-label="成本">
          <h3>成本</h3>
          <dl className="cost-list">
            <div>
              <dt>帧</dt>
              <dd>{state.cost?.frames_captured ?? 0}</dd>
            </div>
            <div>
              <dt>入模</dt>
              <dd>{state.cost?.frames_sent_to_model ?? 0}</dd>
            </div>
            <div>
              <dt>ASR</dt>
              <dd>{state.cost?.asr_calls ?? 0}</dd>
            </div>
            <div>
              <dt>LLM</dt>
              <dd>{state.cost?.vision_llm_calls ?? 0}</dd>
            </div>
            <div>
              <dt>TTS</dt>
              <dd>{state.cost?.tts_calls ?? 0}</dd>
            </div>
          </dl>
        </section>

        {errorMessage ? (
          <section className="rail-error" aria-label="错误">
            <strong>{state.lastError?.stage ?? "media"}</strong>
            <p>{errorMessage}</p>
          </section>
        ) : null}
      </aside>
    </main>
  );
}
