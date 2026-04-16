from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .advisor import PTNKChatAdvisor
from .chat_history import SQLiteChatHistoryStore
from .chunking import TextChunker
from .config import Settings
from .document_loader import DirectoryDocumentLoader
from .openai_client import OpenAIRAGClient
from .pinecone_store import PineconeVectorStore
from .schemas import ChatTurn


class AdmissionsRAGService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.loader = DirectoryDocumentLoader(settings.supported_extensions)
        self.chunker = TextChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        self.openai = OpenAIRAGClient(settings)
        self.vector_store = PineconeVectorStore(settings)
        self.chat_history_store = SQLiteChatHistoryStore(settings.chat_history_db_path)
        self.advisor = PTNKChatAdvisor()

    def ingest_directory(self, data_dir: str | None = None, reset_namespace: bool = False) -> dict:
        self._validate_required_settings()
        directory = Path(data_dir).expanduser() if data_dir else self.settings.data_dir
        documents = self.loader.load_directory(directory)
        chunks = self.chunker.chunk_documents(documents)
        embeddings = self.openai.embed_texts(chunk.text for chunk in chunks)
        indexed_chunks = self.vector_store.upsert_chunks(
            chunks,
            embeddings,
            reset_namespace=reset_namespace,
        )

        return {
            "indexed_files": len(sorted({document.source_name for document in documents})),
            "indexed_documents": len(documents),
            "indexed_chunks": indexed_chunks,
            "index_name": self.settings.pinecone_index_name,
            "namespace": self.settings.pinecone_namespace,
            "files": sorted({document.source_name for document in documents}),
        }

    def answer_question(
        self,
        *,
        message: str,
        history: list[ChatTurn] | None = None,
        top_k: int | None = None,
        session_id: str | None = None,
        channel: str = "api",
        metadata: dict | None = None,
        use_stored_history: bool = True,
        history_limit: int | None = None,
    ) -> dict:
        self._validate_required_settings()
        conversation_history = history or []
        history_source = "request" if conversation_history else "none"

        if session_id and use_stored_history and not conversation_history:
            conversation_history = self.chat_history_store.get_recent_history(
                session_id=session_id,
                channel=channel,
                limit_messages=history_limit or self.settings.history_context_messages,
            )
            history_source = "storage" if conversation_history else "none"

        intent_assessment = self.advisor.assess(message, conversation_history)
        if intent_assessment.needs_clarification:
            result = {
                "intent": intent_assessment.intent,
                "needs_clarification": True,
                "answer": intent_assessment.clarification_question or "Chào bạn, bạn có thể nói rõ hơn giúp mình không?",
                "suggested_replies": intent_assessment.suggested_replies,
                "sources": [],
                "debug": {
                    "intent": intent_assessment.intent,
                    "intent_label": intent_assessment.label,
                    "intent_confidence": intent_assessment.confidence,
                    "matches": 0,
                    "filtered_matches": 0,
                    "namespace": self.settings.pinecone_namespace,
                    "history_source": history_source,
                    "history_messages_used": len(conversation_history),
                },
            }
            assistant_message_id = self._store_exchange(
                session_id=session_id,
                channel=channel,
                user_message=message,
                assistant_message=result["answer"],
                request_metadata={**(metadata or {}), "intent": intent_assessment.intent},
                response_metadata={
                    "intent": intent_assessment.intent,
                    "needs_clarification": True,
                    "suggested_replies": intent_assessment.suggested_replies,
                    "debug": result["debug"],
                },
            )
            result["assistant_message_id"] = assistant_message_id
            if session_id:
                result["debug"]["stored_messages"] = self.chat_history_store.count_messages(
                    session_id=session_id,
                    channel=channel,
                )
            return result

        if self._is_clearly_out_of_scope(
            message=message,
            history=conversation_history,
            intent=intent_assessment.intent,
        ):
            result = {
                "intent": intent_assessment.intent,
                "needs_clarification": False,
                "answer": self._build_out_of_scope_answer(),
                "suggested_replies": [],
                "sources": [],
                "debug": {
                    "intent": intent_assessment.intent,
                    "intent_label": intent_assessment.label,
                    "intent_confidence": intent_assessment.confidence,
                    "matches": 0,
                    "filtered_matches": 0,
                    "namespace": self.settings.pinecone_namespace,
                    "history_source": history_source,
                    "history_messages_used": len(conversation_history),
                    "scope_guard": "out_of_scope",
                },
            }
            assistant_message_id = self._store_exchange(
                session_id=session_id,
                channel=channel,
                user_message=message,
                assistant_message=result["answer"],
                request_metadata={**(metadata or {}), "intent": intent_assessment.intent},
                response_metadata={
                    "intent": intent_assessment.intent,
                    "suggested_replies": [],
                    "sources": [],
                    "debug": result["debug"],
                },
            )
            result["assistant_message_id"] = assistant_message_id
            if session_id:
                result["debug"]["stored_messages"] = self.chat_history_store.count_messages(
                    session_id=session_id,
                    channel=channel,
                )
            return result

        effective_top_k = top_k or self.settings.retrieval_top_k
        retrieval_query = self._build_retrieval_query(message, intent_assessment.intent)
        if intent_assessment.intent in {"admissions_schedule", "mock_exam_schedule"}:
            effective_top_k = max(effective_top_k, 8)
        query_embedding = self.openai.embed_query(retrieval_query)
        if not query_embedding:
            raise ValueError("Khong tao duoc embedding cho cau hoi")

        matches = self.vector_store.query(query_embedding, top_k=effective_top_k)
        filtered_matches = [
            match for match in matches if match.score >= self.settings.min_retrieval_score
        ]
        filtered_matches = self._prioritize_matches(filtered_matches, intent_assessment.intent)

        use_web_fallback = self._should_use_web_fallback(
            message=message,
            history=conversation_history,
            intent=intent_assessment.intent,
            filtered_matches=filtered_matches,
        )
        if use_web_fallback:
            web_result = self.openai.answer_question_with_ptnk_web_search(
                question=message,
                history=conversation_history,
                intent_label=intent_assessment.label,
            )
            if web_result.verified:
                sources = self._build_web_sources(web_result)
                result = {
                    "intent": intent_assessment.intent,
                    "needs_clarification": False,
                    "answer": web_result.answer,
                    "suggested_replies": [],
                    "sources": sources,
                    "debug": {
                        "intent": intent_assessment.intent,
                        "intent_label": intent_assessment.label,
                        "intent_confidence": intent_assessment.confidence,
                        "matches": len(matches),
                        "filtered_matches": len(filtered_matches),
                        "namespace": self.settings.pinecone_namespace,
                        "history_source": history_source,
                        "history_messages_used": len(conversation_history),
                        "web_fallback_used": True,
                        "web_search_verified": True,
                        "web_search_query": web_result.search_query,
                    },
                }
                assistant_message_id = self._store_exchange(
                    session_id=session_id,
                    channel=channel,
                    user_message=message,
                    assistant_message=result["answer"],
                    request_metadata={**(metadata or {}), "intent": intent_assessment.intent},
                    response_metadata={
                        "intent": intent_assessment.intent,
                        "suggested_replies": [],
                        "sources": [
                            {
                                "source_file": source["source_file"],
                                "source_type": source["source_type"],
                                "chunk_index": source["chunk_index"],
                                "score": source["score"],
                                "url": source["url"],
                            }
                            for source in sources
                        ],
                        "debug": result["debug"],
                    },
                )
                result["assistant_message_id"] = assistant_message_id
                if session_id:
                    result["debug"]["stored_messages"] = self.chat_history_store.count_messages(
                        session_id=session_id,
                        channel=channel,
                    )
                return result

        if not filtered_matches:
            result = {
                "intent": intent_assessment.intent,
                "needs_clarification": False,
                "answer": self._build_no_info_answer(intent_assessment),
                "suggested_replies": intent_assessment.suggested_replies,
                "sources": [],
                "debug": {
                    "intent": intent_assessment.intent,
                    "intent_label": intent_assessment.label,
                    "intent_confidence": intent_assessment.confidence,
                    "matches": len(matches),
                    "filtered_matches": 0,
                    "namespace": self.settings.pinecone_namespace,
                    "history_source": history_source,
                    "history_messages_used": len(conversation_history),
                    "web_fallback_used": use_web_fallback,
                },
            }
            assistant_message_id = self._store_exchange(
                session_id=session_id,
                channel=channel,
                user_message=message,
                assistant_message=result["answer"],
                request_metadata={**(metadata or {}), "intent": intent_assessment.intent},
                response_metadata={
                    "intent": intent_assessment.intent,
                    "suggested_replies": intent_assessment.suggested_replies,
                    "sources": [],
                    "debug": result["debug"],
                },
            )
            result["assistant_message_id"] = assistant_message_id
            if session_id:
                result["debug"]["stored_messages"] = self.chat_history_store.count_messages(
                    session_id=session_id,
                    channel=channel,
                )
            return result

        structured_answer = self._build_structured_answer(
            intent=intent_assessment.intent,
            retrieved_chunks=filtered_matches,
        )
        if structured_answer:
            answer = self._apply_response_template(structured_answer)
        else:
            fast_answer = self._build_fast_answer(
                intent=intent_assessment.intent,
                retrieved_chunks=filtered_matches,
            )
            if fast_answer:
                answer = self._apply_response_template(fast_answer)
            else:
                answer = self.openai.answer_question(
                    question=message,
                    retrieved_chunks=filtered_matches,
                    history=conversation_history,
                    intent_label=intent_assessment.label,
                    style_hint=intent_assessment.style_hint,
                )
                answer = self._apply_response_template(answer)

        sources = []
        for match in filtered_matches:
            sources.append(
                {
                    "id": match.id,
                    "source_file": str(match.metadata.get("source_name", "")),
                    "source_type": str(match.metadata.get("source_type", "")),
                    "chunk_index": int(match.metadata.get("chunk_index", 0) or 0),
                    "score": round(match.score, 4),
                    "excerpt": match.text[:280].strip(),
                    "metadata": match.metadata,
                }
            )

        result = {
            "intent": intent_assessment.intent,
            "needs_clarification": False,
            "answer": answer,
            "suggested_replies": intent_assessment.suggested_replies,
            "sources": sources,
            "debug": {
                "intent": intent_assessment.intent,
                "intent_label": intent_assessment.label,
                "intent_confidence": intent_assessment.confidence,
                "matches": len(matches),
                "filtered_matches": len(filtered_matches),
                "namespace": self.settings.pinecone_namespace,
                "history_source": history_source,
                "history_messages_used": len(conversation_history),
            },
        }
        assistant_message_id = self._store_exchange(
            session_id=session_id,
            channel=channel,
            user_message=message,
            assistant_message=answer,
            request_metadata={**(metadata or {}), "intent": intent_assessment.intent},
            response_metadata={
                "intent": intent_assessment.intent,
                "suggested_replies": intent_assessment.suggested_replies,
                "sources": [
                    {
                        "source_file": source["source_file"],
                        "source_type": source["source_type"],
                        "chunk_index": source["chunk_index"],
                        "score": source["score"],
                    }
                    for source in sources
                ],
                "debug": result["debug"],
            },
        )
        result["assistant_message_id"] = assistant_message_id
        if session_id:
            result["debug"]["stored_messages"] = self.chat_history_store.count_messages(
                session_id=session_id,
                channel=channel,
            )
        return result

    def get_chat_history(
        self,
        *,
        session_id: str,
        channel: str = "api",
        limit_messages: int = 50,
    ) -> dict:
        messages = self.chat_history_store.list_messages(
            session_id=session_id,
            channel=channel,
            limit_messages=limit_messages,
        )
        return {
            "session_id": session_id,
            "channel": channel,
            "total_messages": self.chat_history_store.count_messages(
                session_id=session_id,
                channel=channel,
            ),
            "messages": messages,
        }

    def clear_chat_history(self, *, session_id: str, channel: str = "api") -> dict:
        deleted_messages = self.chat_history_store.clear_session(
            session_id=session_id,
            channel=channel,
        )
        return {
            "session_id": session_id,
            "channel": channel,
            "deleted_messages": deleted_messages,
        }

    def save_feedback(
        self,
        *,
        assistant_message_id: int | None,
        session_id: str | None,
        channel: str,
        rating: str,
        note: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        feedback_id = self.chat_history_store.add_feedback(
            assistant_message_id=assistant_message_id,
            session_id=session_id,
            channel=channel,
            rating=rating,
            note=note,
            metadata=metadata or {},
        )
        return {
            "feedback_id": feedback_id,
            "assistant_message_id": assistant_message_id,
            "session_id": session_id,
            "channel": channel,
            "rating": rating,
        }

    def _validate_required_settings(self) -> None:
        missing = self.settings.missing_required_settings()
        if missing:
            raise ValueError(f"Thieu bien moi truong: {', '.join(missing)}")

    def _store_exchange(
        self,
        *,
        session_id: str | None,
        channel: str,
        user_message: str,
        assistant_message: str,
        request_metadata: dict | None,
        response_metadata: dict | None,
    ) -> int | None:
        if not session_id:
            return None
        ids = self.chat_history_store.add_exchange(
            session_id=session_id,
            channel=channel,
            user_message=user_message,
            assistant_message=assistant_message,
            user_metadata=request_metadata or {},
            assistant_metadata=response_metadata or {},
        )
        return ids["assistant_message_id"]

    def _apply_response_template(self, answer: str) -> str:
        return answer.strip()

    def _build_no_info_answer(self, intent_assessment) -> str:
        return (
            "Chào bạn,\n\n"
            "Mình chưa có thông tin xác nhận về nội dung này. "
            "Nếu bạn đang hỏi về PTNK, bạn có thể nhắn rõ hơn một chút hoặc liên hệ qua các kênh sau:\n"
            "Hotline: 1900 9999 17\n"
            "Email: info@ptnk.edu.vn\n"
            "Facebook: http://facebook.com/HSGVNUHCM"
        )

    def _build_out_of_scope_answer(self) -> str:
        return (
            "Chào bạn,\n\n"
            "Mình đang hỗ trợ các thông tin liên quan đến Trường Phổ thông Năng khiếu - Đại học Quốc gia TP.HCM."
        )

    def _build_web_sources(self, web_result) -> list[dict]:
        sources: list[dict] = []
        for index, source in enumerate(web_result.sources):
            sources.append(
                {
                    "id": f"web-{index + 1}",
                    "source_file": source.title or source.url,
                    "source_type": "web",
                    "chunk_index": 0,
                    "score": 1.0,
                    "excerpt": source.snippet[:280].strip(),
                    "url": source.url,
                    "metadata": {
                        "domain": source.domain,
                        "url": source.url,
                        "title": source.title,
                        "source_origin": "web_search",
                    },
                }
            )
        return sources

    def _build_structured_answer(
        self,
        *,
        intent: str,
        retrieved_chunks,
    ) -> str | None:
        if intent == "admissions_schedule":
            return self._build_admissions_schedule_answer(retrieved_chunks)
        if intent == "mock_exam_schedule":
            return self._build_mock_exam_schedule_answer(retrieved_chunks)
        return None

    def _build_fast_answer(
        self,
        *,
        intent: str,
        retrieved_chunks,
    ) -> str | None:
        if not retrieved_chunks:
            return None
        if intent in {"admissions_schedule", "mock_exam_schedule"}:
            return None

        top_match = retrieved_chunks[0]
        if top_match.score < self.settings.fast_answer_score_threshold:
            return None
        if str(top_match.metadata.get("source_type", "")).strip().lower() != "jsonl":
            return None

        content = self._extract_jsonl_content(top_match.text)
        if not content:
            return None
        if len(content) > self.settings.fast_answer_max_chars:
            return None

        return f"Chào bạn,\n\n{content}"

    def _build_admissions_schedule_answer(self, retrieved_chunks) -> str | None:
        schedule_match = next(
            (
                chunk
                for chunk in retrieved_chunks
                if str(chunk.metadata.get("record_category", "")).strip().lower() == "schedule"
                and "tuyen" in chunk.text.lower()
            ),
            None,
        )
        if schedule_match is None:
            schedule_match = next(
                (
                    chunk
                    for chunk in retrieved_chunks
                    if str(chunk.metadata.get("record_category", "")).strip().lower() == "schedule"
                ),
                None,
            )
        if schedule_match is None:
            return None

        text = schedule_match.text
        date_range = self._extract_date_range(text)
        if not date_range:
            return None

        details: list[str] = []
        lowered = text.lower()
        if "khong chuyen vao ngay dau" in lowered or "không chuyên vào ngày đầu" in text.lower():
            details.append(f"Ngày đầu thi các môn không chuyên.")
        if "mon chuyen vao ngay thu hai" in lowered or "môn chuyên vào ngày thứ hai" in text:
            details.append("Ngày thứ hai thi môn chuyên.")

        answer = (
            "Chào bạn,\n\n"
            f"Kỳ thi tuyển sinh lớp 10 PTNK năm học 2026–2027 dự kiến diễn ra trong 2 ngày {date_range}."
        )
        if details:
            answer += " " + " ".join(details)
        return answer

    def _build_mock_exam_schedule_answer(self, retrieved_chunks) -> str | None:
        schedule_match = next(
            (
                chunk
                for chunk in retrieved_chunks
                if str(chunk.metadata.get("record_category", "")).strip().lower() == "schedule"
            ),
            None,
        )
        if schedule_match is None:
            return None

        text = schedule_match.text
        match = re.search(
            r"(ngày\s+\d{1,2}\s+và\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4})",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        return (
            "Chào bạn,\n\n"
            f"Đợt thi thử tiếp theo dự kiến diễn ra vào {match.group(1)}."
        )

    def _extract_date_range(self, text: str) -> str | None:
        match = re.search(r"(\d{1,2}[–-]\d{1,2}/\d{1,2}/\d{4})", text)
        if match:
            value = match.group(1)
            return value.replace("-", "–")
        return None

    def _extract_jsonl_content(self, text: str) -> str:
        patterns = (
            r"^\-\s*content:\s*(.+)$",
            r"^\-\s*answer:\s*(.+)$",
            r"^\-\s*description:\s*(.+)$",
            r"^\-\s*summary:\s*(.+)$",
        )
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            for pattern in patterns:
                match = re.match(pattern, stripped, flags=re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        return ""

    def _build_retrieval_query(self, message: str, intent: str) -> str:
        if intent == "admissions_schedule":
            return f"{message} lich thi ngay thi du kien 2026 mon khong chuyen mon chuyen"
        if intent == "mock_exam_schedule":
            return f"{message} thi thu lich thi thu dot tiep theo ngay thi thu 2026"
        if intent == "exam_structure":
            return f"{message} mon thi tuyen sinh cau truc mon thi toan ngu van tieng anh mon chuyen thi it nhat 4 bai"
        if intent == "admissions_dossier":
            return f"{message} ho so giay to phieu dang ky hoc ba giay khai sinh"
        if intent == "admissions_eligibility":
            return f"{message} dieu kien du thi toan quoc tot nghiep THCS do tuoi"
        if intent == "research_science":
            return f"{message} nckh nghien cuu khoa hoc STEM PRIS lien nganh du an hoc sinh mentor"
        return message

    def _prioritize_matches(self, matches, intent: str):
        if intent == "admissions_schedule":
            return sorted(
                matches,
                key=lambda match: (
                    0 if str(match.metadata.get("record_category", "")).strip().lower() == "schedule" else 1,
                    -match.score,
                ),
            )
        if intent == "mock_exam_schedule":
            return sorted(
                matches,
                key=lambda match: (
                    0 if str(match.metadata.get("record_category", "")).strip().lower() == "schedule" else 1,
                    -match.score,
                ),
            )
        if intent == "admissions_eligibility":
            return sorted(
                matches,
                key=lambda match: (
                    0 if str(match.metadata.get("record_category", "")).strip().lower() == "eligibility" else 1,
                    -match.score,
                ),
            )
        if intent == "exam_structure":
            return sorted(
                matches,
                key=lambda match: (
                    0 if str(match.metadata.get("record_category", "")).strip().lower() == "exam_structure" else 1,
                    -match.score,
                ),
            )
        if intent == "research_science":
            return sorted(
                matches,
                key=lambda match: (
                    0 if (
                        str(match.metadata.get("record_category", "")).strip().lower() == "academics"
                        or "nghien cuu" in match.text.lower()
                        or "stem" in match.text.lower()
                        or "lien nganh" in match.text.lower()
                    ) else 1,
                    -match.score,
                ),
            )
        return matches

    def _should_use_web_fallback(
        self,
        *,
        message: str,
        history: list[ChatTurn],
        intent: str,
        filtered_matches,
    ) -> bool:
        if not self.settings.enable_web_search_fallback:
            return False
        if not self._is_question_about_ptnk(message=message, history=history, intent=intent):
            return False
        if not self._has_external_lookup_signal(message):
            return False
        if not filtered_matches:
            return True
        best_score = max(match.score for match in filtered_matches)
        return best_score < self.settings.web_search_score_threshold

    def _is_clearly_out_of_scope(
        self,
        *,
        message: str,
        history: list[ChatTurn],
        intent: str,
    ) -> bool:
        if intent != "general_support":
            return False
        return not self._is_question_about_ptnk(message=message, history=history, intent=intent)

    def _is_question_about_ptnk(
        self,
        *,
        message: str,
        history: list[ChatTurn],
        intent: str,
    ) -> bool:
        normalized_message = self._normalize_text(message)
        scope_keywords = (
            "ptnk",
            "pho thong nang khieu",
            "nang khieu",
            "cua truong",
            "truong co",
            "o ptnk",
            "hieu truong",
            "pho hieu truong",
            "ban giam hieu",
            "hieu pho",
            "hieu truong truong",
            "lanh dao truong",
            "tuyen sinh",
            "lop 10",
            "mon chuyen",
            "thi thu",
            "ho so",
            "du thi",
            "co so",
            "an dong",
            "thu duc",
            "ngoai khoa",
            "clb",
            "cau lac bo",
            "doan truong",
            "ban chap hanh",
            "bch",
            "nckh",
            "nghien cuu",
            "stem",
            "pris",
            "lien nganh",
            "ignicia",
            "1000days",
            "hsgvnuhcm",
        )
        if any(keyword in normalized_message for keyword in scope_keywords):
            return True
        if self._is_follow_up_question(normalized_message) and self._history_has_ptnk_context(history):
            return True
        return False

    def _history_has_ptnk_context(self, history: list[ChatTurn]) -> bool:
        recent_user_messages = [self._normalize_text(turn.content) for turn in history[-4:] if turn.role == "user"]
        context = " ".join(recent_user_messages)
        if not context:
            return False
        context_markers = (
            "ptnk",
            "pho thong nang khieu",
            "tuyen sinh",
            "lop 10",
            "co so",
            "mon chuyen",
            "nckh",
            "doan truong",
            "lien nganh",
            "ignicia",
            "1000days",
        )
        return any(marker in context for marker in context_markers)

    def _is_follow_up_question(self, normalized_message: str) -> bool:
        follow_up_starters = (
            "con ",
            "con?",
            "them ",
            "the ",
            "vay ",
            "chi tiet",
            "khi nao",
            "bao gio",
            "o dau",
            "le phi",
            "ho so",
            "dieu kien",
            "cau truc",
            "dang ky",
            "lien he",
            "co khong",
        )
        follow_up_markers = (
            "dang ky",
            "dot 2",
            "ho so",
            "dieu kien",
            "cau truc",
            "le phi",
            "lich thi",
            "mon chuyen",
            "ket qua",
            "diem chuan",
            "thong bao",
            "mo dang ky",
            "gia han",
        )
        return any(normalized_message.startswith(starter) for starter in follow_up_starters) or any(
            marker in normalized_message for marker in follow_up_markers
        )

    def _has_external_lookup_signal(self, message: str) -> bool:
        normalized_message = self._normalize_text(message)
        external_markers = (
            "moi nhat",
            "cap nhat",
            "nam nay",
            "hom nay",
            "hieu truong",
            "pho hieu truong",
            "ban giam hieu",
            "hieu pho",
            "lanh dao",
            "hieu truong la ai",
            "thong bao",
            "website",
            "fanpage",
            "facebook",
            "ket qua",
            "diem chuan",
            "han nop",
            "mo dang ky",
            "gia han",
            "vua cong bo",
            "2026",
            "2027",
            "2028",
        )
        return any(marker in normalized_message for marker in external_markers)

    def _normalize_text(self, text: str) -> str:
        normalized = unicodedata.normalize("NFD", text.lower().replace("đ", "d").replace("Đ", "D"))
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return " ".join(normalized.split())
