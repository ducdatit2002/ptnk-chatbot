from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    items = tuple(part.strip() for part in value.split(",") if part.strip())
    return items or default


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    chat_history_db_path: Path
    openai_api_key: str
    openai_chat_model: str
    openai_embedding_model: str
    pinecone_api_key: str
    pinecone_index_name: str
    pinecone_namespace: str
    pinecone_cloud: str
    pinecone_region: str
    pinecone_metric: str
    chunk_size: int
    chunk_overlap: int
    retrieval_top_k: int
    min_retrieval_score: float
    history_context_messages: int
    max_context_characters: int
    openai_timeout_seconds: float
    api_base_url: str
    enable_web_search_fallback: bool
    openai_web_search_model: str
    web_search_allowed_domains: tuple[str, ...]
    web_search_score_threshold: float
    query_embedding_cache_size: int
    fast_answer_score_threshold: float
    fast_answer_max_chars: int

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".json", ".jsonl", ".pdf", ".docx")

    def missing_required_settings(self) -> list[str]:
        missing: list[str] = []
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if not self.pinecone_api_key:
            missing.append("PINECONE_API_KEY or PINE_CONE_API_KEY")
        return missing


@lru_cache
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parent.parent
    return Settings(
        project_root=project_root,
        data_dir=Path(os.getenv("DATA_DIR", str(project_root / "data"))).expanduser(),
        chat_history_db_path=Path(
            os.getenv("CHAT_HISTORY_DB_PATH", str(project_root / "storage" / "chat_history.db"))
        ).expanduser(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-5.2").strip(),
        openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip(),
        pinecone_api_key=(
            os.getenv("PINECONE_API_KEY", "").strip()
            or os.getenv("PINE_CONE_API_KEY", "").strip()
        ),
        pinecone_index_name=os.getenv("PINECONE_INDEX_NAME", "ptnk-admissions-rag").strip(),
        pinecone_namespace=os.getenv("PINECONE_NAMESPACE", "admissions-demo").strip(),
        pinecone_cloud=os.getenv("PINECONE_CLOUD", "aws").strip(),
        pinecone_region=os.getenv("PINECONE_REGION", "us-east-1").strip(),
        pinecone_metric=os.getenv("PINECONE_METRIC", "cosine").strip(),
        chunk_size=_int_env("CHUNK_SIZE", 1000),
        chunk_overlap=_int_env("CHUNK_OVERLAP", 150),
        retrieval_top_k=_int_env("RETRIEVAL_TOP_K", 5),
        min_retrieval_score=_float_env("MIN_RETRIEVAL_SCORE", 0.15),
        history_context_messages=_int_env("HISTORY_CONTEXT_MESSAGES", 12),
        max_context_characters=_int_env("MAX_CONTEXT_CHARACTERS", 6000),
        openai_timeout_seconds=_float_env("OPENAI_TIMEOUT_SECONDS", 60.0),
        api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000").strip(),
        enable_web_search_fallback=_bool_env("ENABLE_WEB_SEARCH_FALLBACK", True),
        openai_web_search_model=os.getenv("OPENAI_WEB_SEARCH_MODEL", "gpt-5").strip(),
        web_search_allowed_domains=_csv_env(
            "WEB_SEARCH_ALLOWED_DOMAINS",
            ("ptnk.edu.vn", "vnuhcm.edu.vn", "facebook.com"),
        ),
        web_search_score_threshold=_float_env("WEB_SEARCH_SCORE_THRESHOLD", 0.35),
        query_embedding_cache_size=_int_env("QUERY_EMBEDDING_CACHE_SIZE", 512),
        fast_answer_score_threshold=_float_env("FAST_ANSWER_SCORE_THRESHOLD", 0.72),
        fast_answer_max_chars=_int_env("FAST_ANSWER_MAX_CHARS", 420),
    )
