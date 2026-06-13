import type { Message } from "../shared/sessionReducer";

type ConversationPanelProps = {
  messages: Message[];
  assistantDraft: string;
};

export function ConversationPanel({ messages, assistantDraft }: ConversationPanelProps) {
  return (
    <section className="panel conversation-panel" aria-label="对话">
      <div className="panel-header">
        <h2>对话</h2>
      </div>
      <div className="message-list">
        {messages.map((message, index) => (
          <article className={`message ${message.role}`} key={`${message.role}-${index}`}>
            <strong>{message.role === "user" ? "你" : "助手"}</strong>
            <p>{message.text}</p>
          </article>
        ))}
        {assistantDraft ? (
          <article className="message assistant">
            <strong>助手</strong>
            <p>{assistantDraft}</p>
          </article>
        ) : null}
      </div>
    </section>
  );
}

