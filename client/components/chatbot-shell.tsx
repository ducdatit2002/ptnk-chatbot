"use client";

import Image from "next/image";
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";

import { ChatMessage } from "@/components/chat-message";
import { createSessionId } from "@/lib/session";
import type { ChatApiResponse, ChatMessageItem, ChatSource } from "@/lib/types";

type ChatErrorPayload = {
  detail?: string;
  error?: string;
};

const APP_NAME =
  process.env.NEXT_PUBLIC_APP_NAME?.trim() || "Chatbot Trường Phổ thông Năng khiếu - Đại học Quốc gia TP.HCM";

const starterPrompts = [
  "Trường có những cơ sở nào?",
  "Cách đăng ký thi vào lớp 10 như thế nào?",
  "Môi trường học tập của trường có gì nổi bật?",
  "Trường có hoạt động ngoại khóa nào?",
];

const welcomeMessage: ChatMessageItem = {
  id: "welcome-message",
  role: "assistant",
  content:
    "Chào bạn, mình là trợ lý hỏi đáp về Trường Phổ thông Năng khiếu. Bạn có thể hỏi về tuyển sinh, cơ sở học tập, môi trường học, hoạt động học sinh hoặc lịch thi thử.",
  suggestedReplies: starterPrompts,
};

export function ChatbotShell() {
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState<ChatMessageItem[]>([welcomeMessage]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setSessionId(createSessionId());
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  useEffect(() => {
    let cancelled = false;

    async function checkHealth() {
      try {
        const response = await fetch("/api/health", { cache: "no-store" });
        if (!response.ok) {
          throw new Error("health check failed");
        }

        if (!cancelled) {
          setBackendStatus("online");
        }
      } catch {
        if (!cancelled) {
          setBackendStatus("offline");
        }
      }
    }

    void checkHealth();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event?: FormEvent<HTMLFormElement>, presetMessage?: string) {
    event?.preventDefault();

    const trimmed = (presetMessage ?? input).trim();
    if (!trimmed || isSending || !sessionId) {
      return;
    }

    const nextUserMessage: ChatMessageItem = {
      id: `${Date.now()}-user`,
      role: "user",
      content: trimmed,
    };

    const history = messages
      .filter((message) => message.role === "user" || message.role === "assistant")
      .map((message) => ({
        role: message.role,
        content: message.content,
      }));

    setMessages((current) => [...current, nextUserMessage]);
    setInput("");
    setIsSending(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: sessionId,
          channel: "web",
          message: trimmed,
          history,
          use_stored_history: true,
        }),
      });

      const payload = (await response.json()) as ChatApiResponse | ChatErrorPayload;

      if (!response.ok) {
        throw new Error(
          "detail" in payload && payload.detail
            ? payload.detail
            : "error" in payload && payload.error
              ? payload.error
              : "Đã có lỗi xảy ra khi gửi tin nhắn.",
        );
      }

      const data = payload as ChatApiResponse;

      const assistantMessage: ChatMessageItem = {
        id: `${Date.now()}-assistant`,
        role: "assistant",
        content: sanitizeAssistantMessage(data.answer),
        suggestedReplies: normalizeSuggestedReplies(data.suggested_replies),
        sources: normalizeSources(data.sources),
      };

      setMessages((current) => [...current, assistantMessage]);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Không thể gửi tin nhắn lúc này.";

      setMessages((current) => [
        ...current,
        {
          id: `${Date.now()}-error`,
          role: "assistant",
          content:
            "Chào bạn, hiện tại kết nối đến hệ thống đang gặp vấn đề. Bạn thử lại sau ít phút hoặc kiểm tra cấu hình backend giúp mình nhé.",
          error: message,
        },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }

    event.preventDefault();
    void handleSubmit(undefined);
  }

  function handleReset() {
    setSessionId(createSessionId());
    setMessages([welcomeMessage]);
  }

  return (
    <main className="app-shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />

      <section className="chat-panel">
        <header className="chat-header">
          <div className="brand-block">
            <Image
              src="/logo-ptnk.png"
              alt="Logo Trường Phổ thông Năng khiếu"
              width={56}
              height={56}
              className="brand-logo"
              priority
            />
            <div>
            <p className="eyebrow">Trò chuyện cùng chatbot</p>
            <h2>{APP_NAME}</h2>
            </div>
          </div>
          <span className={`status-dot status-${backendStatus}`} aria-label={`backend-${backendStatus}`} />
          <button className="ghost-button" type="button" onClick={handleReset}>
            Cuộc trò chuyện mới
          </button>
        </header>

        <div className="message-list">
          {messages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message}
              onPromptClick={(prompt) => void handleSubmit(undefined, prompt)}
            />
          ))}

          {isSending ? (
            <div className="typing-row">
              <span />
              <span />
              <span />
            </div>
          ) : null}

          <div ref={messagesEndRef} />
        </div>

        <form className="chat-form" onSubmit={(event) => void handleSubmit(event)}>
          <label className="input-wrap">
            <span className="sr-only">Nhập câu hỏi</span>
            <textarea
              rows={1}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Nhập câu hỏi, ví dụ: trường có mấy cơ sở học?"
            />
          </label>
          <button className="send-button" type="submit" disabled={isSending || !input.trim()}>
            Gửi
          </button>
        </form>
      </section>
    </main>
  );
}

function normalizeSources(sources: ChatSource[] | undefined): ChatSource[] {
  if (!Array.isArray(sources)) {
    return [];
  }
  return sources.map((source) => ({
    id: source.id,
    source_file: source.source_file,
    source_type: source.source_type,
    chunk_index: source.chunk_index,
    score: source.score,
    excerpt: source.excerpt,
    url: source.url,
    metadata: source.metadata,
  }));
}

function sanitizeAssistantMessage(content: string) {
  return content
    .replace(
      /(?:Một vài điểm nổi bật về|Những điểm nổi bật về|Một số thông tin về)\s+([^.!?\n]+?)\s+mà mình có thông tin chắc chắn là:\s*/gi,
      "$1:\n",
    )
    .replace(
      /(?:Mình có thông tin chắc chắn là|Mình có thông tin xác nhận là|Mình có thông tin chắc chắn về nội dung này là)\s*/gi,
      "",
    )
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function normalizeSuggestedReplies(replies: string[] | undefined) {
  if (!Array.isArray(replies)) {
    return [];
  }

  return replies.map((reply) => accentizeSuggestion(reply));
}

function accentizeSuggestion(text: string) {
  const normalized = text.trim().toLowerCase();
  const dictionary: Record<string, string> = {
    "truong co nhung co so nao?": "Trường có những cơ sở nào?",
    "thu vien cua truong nhu the nao?": "Thư viện của trường như thế nào?",
    "phuong tien di den truong ra sao?": "Phương tiện đi đến trường ra sao?",
    "truong co nhung hoat dong ngoai khoa nao?": "Trường có những hoạt động ngoại khóa nào?",
    "truong co hoat dong ngoai khoa nao?": "Trường có hoạt động ngoại khóa nào?",
    "cach dang ky thi vao lop 10 nhu the nao?": "Cách đăng ký thi vào lớp 10 như thế nào?",
    "moi truong hoc tap cua truong co gi noi bat?": "Môi trường học tập của trường có gì nổi bật?",
    "truong co may co so hoc?": "Trường có mấy cơ sở học?",
    "ho so dang ky gom gi?": "Hồ sơ đăng ký gồm gì?",
  };

  return dictionary[normalized] || text;
}
