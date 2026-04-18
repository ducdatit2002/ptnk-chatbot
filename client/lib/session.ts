import type { ChatMessageItem } from "@/lib/types";

const STORAGE_KEY = "ptnk-chatbot-session";

type StoredSession = {
  sessionId: string;
  messages: ChatMessageItem[];
};

export function createSessionId() {
  return `web-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function loadStoredSession(): StoredSession | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as StoredSession;
  } catch {
    return null;
  }
}

export function persistStoredSession(sessionId: string, messages: ChatMessageItem[]) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      sessionId,
      messages,
    }),
  );
}
