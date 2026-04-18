import type { ChatMessageItem } from "@/lib/types";

type ChatMessageProps = {
  message: ChatMessageItem;
  onPromptClick: (prompt: string) => void;
};

export function ChatMessage({ message, onPromptClick }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <article className={`message-row ${isUser ? "message-user" : "message-assistant"}`}>
      <div className="avatar">{isUser ? "Bạn" : "PTNK"}</div>
      <div className="bubble-wrap">
        <div className={`message-bubble ${isUser ? "bubble-user" : "bubble-assistant"}`}>
          <div className="message-content">{renderFormattedContent(message.content)}</div>
          {message.error ? <small className="error-note">{message.error}</small> : null}
        </div>

        {message.suggestedReplies?.length ? (
          <div className="prompt-list">
            {message.suggestedReplies.slice(0, 4).map((prompt) => (
              <button
                key={prompt}
                className="prompt-chip"
                type="button"
                onClick={() => onPromptClick(prompt)}
              >
                {prompt}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </article>
  );
}

function renderFormattedContent(content: string) {
  return content.split("\n").map((line, lineIndex) => (
    <p key={`${line}-${lineIndex}`}>{renderInlineBold(line)}</p>
  ));
}

function renderInlineBold(line: string) {
  const parts = line.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).filter(Boolean);

  return parts.map((part, index) => {
    const boldMatch = part.match(/^\*\*([^*]+)\*\*$|^\*([^*]+)\*$/);
    if (boldMatch) {
      return <strong key={`${part}-${index}`}>{boldMatch[1] || boldMatch[2]}</strong>;
    }
    return <span key={`${part}-${index}`}>{part}</span>;
  });
}
