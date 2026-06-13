import type { CostSnapshot } from "../types/events";

type CostPanelProps = {
  cost: CostSnapshot | null;
};

export function CostPanel({ cost }: CostPanelProps) {
  return (
    <section className="panel cost-panel" aria-label="成本控制">
      <div className="panel-header">
        <h2>成本控制</h2>
      </div>
      <dl className="cost-grid">
        <div>
          <dt>抽帧数</dt>
          <dd>{cost?.frames_captured ?? 0}</dd>
        </div>
        <div>
          <dt>入模关键帧</dt>
          <dd>{cost?.frames_sent_to_model ?? 0}</dd>
        </div>
        <div>
          <dt>ASR</dt>
          <dd>{cost?.asr_calls ?? 0}</dd>
        </div>
        <div>
          <dt>视觉问答</dt>
          <dd>{cost?.vision_llm_calls ?? 0}</dd>
        </div>
        <div>
          <dt>TTS</dt>
          <dd>{cost?.tts_calls ?? 0}</dd>
        </div>
        <div>
          <dt>策略</dt>
          <dd>{cost?.policy ?? "normal"}</dd>
        </div>
      </dl>
    </section>
  );
}

