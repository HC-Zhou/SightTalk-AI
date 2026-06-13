import { Mic, Play, Square } from "lucide-react";
import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { CostPanel } from "./components/CostPanel";
import { ConversationPanel } from "./components/ConversationPanel";
import { StatusBar } from "./components/StatusBar";
import { VideoPreview } from "./components/VideoPreview";
import { useCameraSampler } from "./hooks/useCameraSampler";
import { useMicrophoneRecorder } from "./hooks/useMicrophoneRecorder";
import { initialSessionState, sessionReducer } from "./shared/sessionReducer";
import { type ClientStatus, VisionSessionClient } from "./shared/wsClient";

const SESSION_ID = "demo-session";
const API_ORIGIN = "http://127.0.0.1:8000";

export default function App() {
  const [state, dispatch] = useReducer(sessionReducer, initialSessionState);
  const [transportStatus, setTransportStatus] = useState<ClientStatus | "idle">("idle");
  const clientRef = useRef<VisionSessionClient | null>(null);
  const camera = useCameraSampler(state.policy);
  const microphone = useMicrophoneRecorder();

  const wsUrl = useMemo(() => {
    return `ws://127.0.0.1:8000/ws/session/${SESSION_ID}`;
  }, []);

  useEffect(() => {
    if (!state.ttsUrl) {
      return;
    }
    const audio = new Audio(`${API_ORIGIN}${state.ttsUrl}`);
    void audio.play();
  }, [state.ttsUrl]);

  const startSession = async () => {
    clientRef.current?.close();
    const client = new VisionSessionClient({
      url: wsUrl,
      onEvent: dispatch,
      onStatus: setTransportStatus
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
    clientRef.current?.send({ type: "session.stop" });
    clientRef.current?.close();
    clientRef.current = null;
    setTransportStatus("closed");
  };

  const errorMessage = state.errorMessage ?? camera.errorMessage ?? microphone.errorMessage;

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">SightTalk AI</p>
          <h1>AI 视觉对话助手</h1>
          <p>摄像头、麦克风、WebSocket 会话、Mock ASR/视觉问答/TTS 与成本控制。</p>
        </div>
        <div className="header-actions">
          <button type="button" onClick={startSession}>
            <Play aria-hidden="true" size={18} />
            开始
          </button>
          <button type="button" onClick={endUtterance}>
            <Mic aria-hidden="true" size={18} />
            我说完了
          </button>
          <button type="button" onClick={stopSession}>
            <Square aria-hidden="true" size={18} />
            停止
          </button>
        </div>
      </header>

      <StatusBar
        connectionStatus={`${transportStatus}/${state.connectionStatus}`}
        cameraStatus={camera.status}
        microphoneStatus={microphone.status}
        errorMessage={errorMessage}
      />

      <section className="workspace-grid">
        <VideoPreview videoRef={camera.videoRef} />
        <ConversationPanel messages={state.messages} assistantDraft={state.assistantDraft} />
        <CostPanel cost={state.cost} />
      </section>
    </main>
  );
}
