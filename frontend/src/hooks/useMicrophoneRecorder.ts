import { useCallback, useRef, useState } from "react";
import { blobToBase64 } from "../types/events";

export type CapturedAudioChunk = {
  seq: number;
  mime: string;
  data: string;
};

export function useMicrophoneRecorder() {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const seqRef = useRef(0);
  const [status, setStatus] = useState<"idle" | "recording" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const start = useCallback(async (onChunk: (chunk: CapturedAudioChunk) => void) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      recorderRef.current = recorder;
      recorder.ondataavailable = async (event) => {
        if (event.data.size === 0) {
          return;
        }
        const data = await blobToBase64(event.data);
        onChunk({
          seq: seqRef.current,
          mime: event.data.type || "audio/webm",
          data
        });
        seqRef.current += 1;
      };
      recorder.start(1000);
      setErrorMessage(null);
      setStatus("recording");
    } catch (error) {
      setStatus("error");
      setErrorMessage(error instanceof Error ? error.message : "Microphone permission failed");
    }
  }, []);

  const markUtteranceEnd = useCallback(() => {
    recorderRef.current?.requestData();
    return Math.max(0, seqRef.current - 1);
  }, []);

  const stop = useCallback(() => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setStatus("idle");
  }, []);

  return { status, errorMessage, start, markUtteranceEnd, stop };
}
