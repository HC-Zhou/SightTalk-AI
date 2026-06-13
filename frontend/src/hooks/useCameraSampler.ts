import { useCallback, useRef, useState } from "react";
import type { CapturePolicy } from "../types/events";

export type CapturedFrame = {
  seq: number;
  mime: "image/jpeg";
  captured_at: number;
  data: string;
};

export function useCameraSampler(policy: CapturePolicy | null) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);
  const seqRef = useRef(0);
  const [status, setStatus] = useState<"idle" | "active" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const stop = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setStatus("idle");
  }, []);

  const start = useCallback(
    async (onFrame: (frame: CapturedFrame) => void) => {
      stop();
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        setErrorMessage(null);
        setStatus("active");

        const capture = () => {
          const video = videoRef.current;
          if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
            return;
          }

          const maxWidth = policy?.image_max_width ?? 640;
          const scale = Math.min(1, maxWidth / video.videoWidth);
          const width = Math.round(video.videoWidth * scale);
          const height = Math.round(video.videoHeight * scale);
          const canvas = document.createElement("canvas");
          canvas.width = width;
          canvas.height = height;
          const context = canvas.getContext("2d");
          if (!context) {
            return;
          }
          context.drawImage(video, 0, 0, width, height);
          const dataUrl = canvas.toDataURL("image/jpeg", policy?.jpeg_quality ?? 0.7);
          onFrame({
            seq: seqRef.current,
            mime: "image/jpeg",
            captured_at: Date.now(),
            data: dataUrl.split(",")[1] ?? ""
          });
          seqRef.current += 1;
        };

        capture();
        timerRef.current = window.setInterval(capture, policy?.frame_interval_ms ?? 2000);
      } catch (error) {
        setStatus("error");
        setErrorMessage(error instanceof Error ? error.message : "Camera permission failed");
      }
    },
    [policy, stop]
  );

  return { videoRef, status, errorMessage, start, stop };
}

