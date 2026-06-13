import { useCallback, useRef, useState } from 'react';

export const mediaConstraints: MediaStreamConstraints = {
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  },
  video: {
    width: { ideal: 1280 },
    height: { ideal: 720 },
    frameRate: { ideal: 30, max: 30 },
  },
};

export function useLocalMedia() {
  const [stream, setStream] = useState<MediaStream | undefined>();
  const streamRef = useRef<MediaStream | undefined>(undefined);

  const requestMedia = useCallback(async () => {
    const nextStream = await navigator.mediaDevices.getUserMedia(mediaConstraints);
    streamRef.current = nextStream;
    setStream(nextStream);
    return nextStream;
  }, []);

  const stopMedia = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = undefined;
    setStream(undefined);
  }, []);

  return { stream, requestMedia, stopMedia };
}
