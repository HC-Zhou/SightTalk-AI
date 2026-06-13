import type { RefObject } from "react";

type VideoPreviewProps = {
  videoRef: RefObject<HTMLVideoElement>;
};

export function VideoPreview({ videoRef }: VideoPreviewProps) {
  return (
    <section className="panel video-panel" aria-label="摄像头预览">
      <div className="panel-header">
        <h2>摄像头</h2>
      </div>
      <video ref={videoRef} muted playsInline className="video-preview" />
    </section>
  );
}
