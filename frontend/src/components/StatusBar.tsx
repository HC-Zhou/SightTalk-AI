type StatusBarProps = {
  connectionStatus: string;
  cameraStatus: string;
  microphoneStatus: string;
  errorMessage: string | null;
};

export function StatusBar({
  connectionStatus,
  cameraStatus,
  microphoneStatus,
  errorMessage
}: StatusBarProps) {
  return (
    <section className="status-bar" aria-label="状态">
      <span>连接：{connectionStatus}</span>
      <span>摄像头：{cameraStatus}</span>
      <span>麦克风：{microphoneStatus}</span>
      {errorMessage ? <strong>{errorMessage}</strong> : null}
    </section>
  );
}

