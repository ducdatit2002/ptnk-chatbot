from __future__ import annotations

import json
import sys
from pathlib import Path

import requests
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings


settings = get_settings()


def load_runtime_urls() -> dict[str, str]:
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


def resolve_public_api_url() -> str:
    runtime_urls = load_runtime_urls()
    return runtime_urls.get("api_public_url") or settings.public_base_url


def is_local_api_url(url: str) -> bool:
    return url.startswith("http://localhost:") or url.startswith("http://127.0.0.1:")


def call_api(
    method: str,
    path: str,
    *,
    timeout: int,
    **kwargs: object,
) -> requests.Response:
    current_base_url = st.session_state.api_base_url.rstrip("/")
    fallback_public_url = resolve_public_api_url().rstrip("/")
    candidate_urls = [current_base_url]

    if (
        fallback_public_url
        and fallback_public_url != current_base_url
        and is_local_api_url(current_base_url)
    ):
        candidate_urls.append(fallback_public_url)

    last_exc: requests.RequestException | None = None
    for candidate_base_url in candidate_urls:
        try:
            response = requests.request(
                method,
                f"{candidate_base_url}{path}",
                timeout=timeout,
                **kwargs,
            )
            response.raise_for_status()
            if candidate_base_url != current_base_url:
                st.session_state.api_base_url = candidate_base_url
            return response
        except requests.RequestException as exc:
            last_exc = exc

    if last_exc is None:
        raise RuntimeError("Khong xac dinh duoc loi goi API.")
    raise last_exc

st.set_page_config(
    page_title="PTNK Admissions RAG Tester",
    layout="wide",
)

st.title("Chatbot hỏi đáp về Trường Phổ thông Năng khiếu - Đại học Quốc gia TP.HCM")
st.caption("")
public_api_url = resolve_public_api_url()
if public_api_url:
    st.info(f"Public API URL: {public_api_url}")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "api_base_url" not in st.session_state:
    st.session_state.api_base_url = public_api_url or settings.api_base_url

with st.sidebar:
    st.header("API Config")
    api_base_url = st.text_input("API Base URL", key="api_base_url").rstrip("/")
    session_id = st.text_input("Session ID", value="streamlit-demo-user")
    channel = st.text_input("Channel", value="streamlit")
    use_stored_history = st.checkbox("Dung lich su luu tren API", value=True)
    reset_namespace = st.checkbox("Reset namespace khi ingest", value=False)

    if st.button("Ingest data/ vao Pinecone", use_container_width=True):
        try:
            response = call_api(
                "post",
                "/ingest",
                json={"reset_namespace": reset_namespace},
                timeout=300,
            )
            st.success("Ingest thanh cong")
            st.json(response.json())
        except requests.RequestException as exc:
            st.error(f"Khong goi duoc API ingest: {exc}")

    if st.button("Xoa lich su chat tren UI", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    if st.button("Xoa lich su session tren API", use_container_width=True):
        try:
            response = call_api(
                "delete",
                f"/sessions/{session_id}/history",
                params={"channel": channel},
                timeout=60,
            )
            st.success("Da xoa lich su session tren API")
            st.json(response.json())
        except requests.RequestException as exc:
            st.error(f"Khong xoa duoc lich su session: {exc}")


def build_history_payload() -> list[dict[str, str]]:
    if use_stored_history:
        return []
    return [
        {"role": item["role"], "content": item["content"]}
        for item in st.session_state.messages
        if item["role"] in {"user", "assistant"}
    ]


def submit_question(question: str) -> None:
    clean_question = question.strip()
    if not clean_question:
        return

    history_payload = build_history_payload()
    st.session_state.messages.append({"role": "user", "content": clean_question})
    try:
        response = call_api(
            "post",
            "/chat",
            json={
                "session_id": session_id,
                "channel": channel,
                "message": clean_question,
                "history": history_payload,
                "use_stored_history": use_stored_history,
            },
            timeout=180,
        )
        result = response.json()
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": result["answer"],
                "sources": result.get("sources", []),
            }
        )
    except requests.RequestException as exc:
        error_message = f"Khong goi duoc API chat: {exc}"
        st.session_state.messages.append(
            {"role": "assistant", "content": error_message, "sources": []}
        )


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("sources"):
            with st.expander("Nguon retrieve"):
                st.json(message["sources"])

question = st.chat_input("Hoi ve tuyen sinh PTNK...")
if question:
    submit_question(question)
    st.rerun()
