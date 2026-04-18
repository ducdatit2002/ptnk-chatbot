export type ApiTurn = {
  role: "user" | "assistant";
  content: string;
};

export type ChatSource = {
  id: string;
  source_file: string;
  source_type: string;
  chunk_index: number;
  score: number;
  excerpt: string;
  url?: string | null;
  metadata?: Record<string, unknown>;
};

export type ChatApiResponse = {
  session_id?: string | null;
  channel: string;
  intent: string;
  needs_clarification: boolean;
  answer: string;
  suggested_replies: string[];
  assistant_message_id?: number | null;
  sources: ChatSource[];
  debug: Record<string, unknown>;
};

export type ChatMessageItem = {
  id: string;
  role: "user" | "assistant";
  content: string;
  error?: string;
  suggestedReplies?: string[];
  sources?: ChatSource[];
};
