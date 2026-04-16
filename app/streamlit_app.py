from __future__ import annotations

import sys
from pathlib import Path

import requests
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings


settings = get_settings()

st.set_page_config(
    page_title="PTNK Admissions RAG Tester",
    layout="wide",
)

st.title("Chatbot hỏi đáp về Trường Phổ thông Năng khiếu - Đại học Quốc gia TP.HCM")
st.caption("")

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("API Config")
    api_base_url = st.text_input("API Base URL", value=settings.api_base_url).rstrip("/")
    session_id = st.text_input("Session ID", value="streamlit-demo-user")
    channel = st.text_input("Channel", value="streamlit")
    use_stored_history = st.checkbox("Dung lich su luu tren API", value=True)
    reset_namespace = st.checkbox("Reset namespace khi ingest", value=False)

    if st.button("Ingest data/ vao Pinecone", use_container_width=True):
        try:
            response = requests.post(
                f"{api_base_url}/ingest",
                json={"reset_namespace": reset_namespace},
                timeout=300,
            )
            response.raise_for_status()
            st.success("Ingest thanh cong")
            st.json(response.json())
        except requests.RequestException as exc:
            st.error(f"Khong goi duoc API ingest: {exc}")

    if st.button("Xoa lich su chat tren UI", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    if st.button("Xoa lich su session tren API", use_container_width=True):
        try:
            response = requests.delete(
                f"{api_base_url}/sessions/{session_id}/history",
                params={"channel": channel},
                timeout=60,
            )
            response.raise_for_status()
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
        response = requests.post(
            f"{api_base_url}/chat",
            json={
                "session_id": session_id,
                "channel": channel,
                "message": clean_question,
                "history": history_payload,
                "use_stored_history": use_stored_history,
            },
            timeout=180,
        )
        response.raise_for_status()
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
