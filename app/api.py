from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from .config import get_settings
from .rag_service import AdmissionsRAGService
from .schemas import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ClearHistoryResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
)


settings = get_settings()
service = AdmissionsRAGService(settings)

app = FastAPI(
    title="PTNK Admissions RAG API",
    version="0.1.0",
    description="API hoi dap tuyen sinh bang RAG voi OpenAI va Pinecone.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_runtime_urls() -> dict[str, str]:
    path = settings.runtime_urls_path
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items() if value}


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    missing = settings.missing_required_settings()
    return HealthResponse(
        status="ok" if not missing else "missing_config",
        openai_configured=bool(settings.openai_api_key),
        pinecone_configured=bool(settings.pinecone_api_key),
        index_name=settings.pinecone_index_name,
        namespace=settings.pinecone_namespace,
        data_dir=str(settings.data_dir),
        chat_history_db_path=str(settings.chat_history_db_path),
        supported_extensions=list(settings.supported_extensions),
        public_base_url=settings.public_base_url or None,
    )


@app.get("/streamlit", include_in_schema=False, response_model=None)
def open_streamlit(request: Request) -> Response:
    runtime_urls = _load_runtime_urls()
    target_url = runtime_urls.get("streamlit_public_url") or settings.streamlit_public_url
    if target_url:
        return RedirectResponse(url=target_url, status_code=307)

    if request.url.hostname in {"127.0.0.1", "localhost"} and settings.streamlit_local_url:
        return RedirectResponse(url=settings.streamlit_local_url, status_code=307)

    return HTMLResponse(
        content=(
            "<html><body>"
            "<h3>Streamlit public URL chua san sang</h3>"
            "<p>Hay chay lai <code>bash scripts/run_api_ngrok.sh</code> de mo tunnel cho Streamlit.</p>"
            "</body></html>"
        ),
        status_code=503,
    )


@app.post("/ingest", response_model=IngestResponse)
def ingest_documents(payload: IngestRequest) -> IngestResponse:
    try:
        result = service.ingest_directory(
            data_dir=payload.data_dir,
            reset_namespace=payload.reset_namespace,
        )
        return IngestResponse(**result)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    try:
        result = service.answer_question(
            message=payload.message,
            history=payload.history,
            top_k=payload.top_k,
            session_id=payload.session_id,
            channel=payload.channel,
            metadata=payload.metadata,
            use_stored_history=payload.use_stored_history,
            history_limit=payload.history_limit,
        )
        return ChatResponse(
            session_id=payload.session_id,
            channel=payload.channel,
            intent=result["intent"],
            needs_clarification=result["needs_clarification"],
            answer=result["answer"],
            suggested_replies=result["suggested_replies"],
            assistant_message_id=result.get("assistant_message_id"),
            sources=result["sources"],
            debug=result["debug"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(payload: FeedbackRequest) -> FeedbackResponse:
    try:
        result = service.save_feedback(
            assistant_message_id=payload.assistant_message_id,
            session_id=payload.session_id,
            channel=payload.channel,
            rating=payload.rating,
            note=payload.note,
            metadata=payload.metadata,
        )
        return FeedbackResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/sessions/{session_id}/history", response_model=ChatHistoryResponse)
def get_session_history(
    session_id: str,
    channel: str = Query(default="api"),
    limit: int = Query(default=50, ge=1, le=500),
) -> ChatHistoryResponse:
    try:
        result = service.get_chat_history(
            session_id=session_id,
            channel=channel,
            limit_messages=limit,
        )
        return ChatHistoryResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/sessions/{session_id}/history", response_model=ClearHistoryResponse)
def clear_session_history(
    session_id: str,
    channel: str = Query(default="api"),
) -> ClearHistoryResponse:
    try:
        result = service.clear_chat_history(
            session_id=session_id,
            channel=channel,
        )
        return ClearHistoryResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
