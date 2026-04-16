from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    session_id: str | None = None
    channel: str = "api"
    message: str = Field(min_length=1)
    history: list[ChatTurn] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    use_stored_history: bool = True
    history_limit: int | None = Field(default=None, ge=1, le=100)
    top_k: int | None = Field(default=None, ge=1, le=20)


class SourceItem(BaseModel):
    id: str
    source_file: str
    source_type: str
    chunk_index: int
    score: float
    excerpt: str
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    session_id: str | None = None
    channel: str = "api"
    intent: str = "general_support"
    needs_clarification: bool = False
    answer: str
    suggested_replies: list[str] = Field(default_factory=list)
    assistant_message_id: int | None = None
    sources: list[SourceItem] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    data_dir: str | None = None
    reset_namespace: bool = False


class IngestResponse(BaseModel):
    indexed_files: int
    indexed_documents: int
    indexed_chunks: int
    index_name: str
    namespace: str
    files: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    openai_configured: bool
    pinecone_configured: bool
    index_name: str
    namespace: str
    data_dir: str
    chat_history_db_path: str
    supported_extensions: list[str]


class StoredChatMessage(BaseModel):
    id: int
    session_id: str
    channel: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatHistoryResponse(BaseModel):
    session_id: str
    channel: str
    total_messages: int
    messages: list[StoredChatMessage] = Field(default_factory=list)


class ClearHistoryResponse(BaseModel):
    session_id: str
    channel: str
    deleted_messages: int


class FeedbackRequest(BaseModel):
    assistant_message_id: int | None = None
    session_id: str | None = None
    channel: str = "api"
    rating: Literal["helpful", "not_helpful"]
    note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackResponse(BaseModel):
    feedback_id: int
    assistant_message_id: int | None = None
    session_id: str | None = None
    channel: str
    rating: Literal["helpful", "not_helpful"]
