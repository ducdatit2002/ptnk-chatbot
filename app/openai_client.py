from __future__ import annotations

import re
import unicodedata
from collections import OrderedDict
from urllib.parse import urlparse
from typing import Iterable

from openai import OpenAI

from .config import Settings
from .schemas import ChatTurn
from .types import RetrievedChunk, WebSearchResult, WebSource


class OpenAIRAGClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_seconds,
        )
        self._query_embedding_cache: OrderedDict[str, list[float]] = OrderedDict()

    def _responses_kwargs(self, *, model: str) -> dict:
        kwargs: dict = {"model": model}
        normalized = model.strip().lower()
        if normalized.startswith("gpt-5"):
            kwargs["reasoning"] = {"effort": "low"}
        return kwargs

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        clean_texts = [text.strip() for text in texts if text and text.strip()]
        if not clean_texts:
            return []

        response = self.client.embeddings.create(
            model=self.settings.openai_embedding_model,
            input=clean_texts,
            encoding_format="float",
        )
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        normalized = " ".join(text.strip().split())
        if not normalized:
            return []

        cached = self._query_embedding_cache.get(normalized)
        if cached is not None:
            self._query_embedding_cache.move_to_end(normalized)
            return list(cached)

        embeddings = self.embed_texts([normalized])
        if not embeddings:
            return []

        embedding = embeddings[0]
        self._query_embedding_cache[normalized] = embedding
        while len(self._query_embedding_cache) > self.settings.query_embedding_cache_size:
            self._query_embedding_cache.popitem(last=False)
        return list(embedding)

    def answer_question(
        self,
        *,
        question: str,
        retrieved_chunks: list[RetrievedChunk],
        history: list[ChatTurn],
        intent_label: str,
        style_hint: str,
    ) -> str:
        instructions = (
            "Bạn là chatbot tư vấn cho Trường Phổ thông Năng khiếu. "
            "Chỉ trả lời những gì có thể xác nhận từ thông tin nội bộ đã được cung cấp, "
            "không tự suy đoán thêm học phí, chỉ tiêu, lịch, điều kiện, email, link hay quy trình nếu không chắc chắn. "
            "Ưu tiên tiếng Việt tự nhiên, mượt, ngắn gọn, giống đang trả lời trực tiếp cho học sinh trên Messenger. "
            "Giọng điệu thân thiện, sáng sủa, dễ hiểu, hợp với học sinh cấp 2 hoặc cấp 3. "
            "Xưng hô theo kiểu 'mình' và 'bạn'. "
            "Câu ngắn, rõ, ít văn hành chính. Nếu có nhiều ý thì tách dòng hoặc gạch đầu dòng ngắn để dễ đọc. "
            "Không dùng teencode, không cố nhồi slang, không nói kiểu quá người lớn hoặc quá giáo điều. "
            "Mỗi câu trả lời phải bắt đầu bằng 'Chào bạn,'. "
            "Không nhắc đến các từ hoặc ý như 'tài liệu', 'dữ liệu', 'ngữ cảnh', 'nguồn', 'truy xuất', "
            "'theo tài liệu', 'theo dữ liệu', 'trong tài liệu', hay 'dựa trên thông tin được cung cấp'. "
            "Nếu chưa có đủ thông tin chắc chắn, hãy nói tự nhiên rằng hiện mình chưa có thông tin xác nhận về nội dung đó, "
            "không giải thích rằng bạn không tìm thấy trong tài liệu. "
            "Chỉ trả lời đúng nội dung người dùng đang hỏi. "
            "Không tự thêm câu mời hỏi tiếp, không gợi ý chủ đề khác, không giới thiệu thêm dịch vụ, "
            "không chèn hotline, fanpage, website hay thông tin liên hệ nếu người dùng không hỏi và bạn vẫn trả lời được câu hỏi chính. "
            "Không thêm các câu kết kiểu 'Nếu bạn muốn...', 'Nếu bạn cần...', 'Mình có thể gửi thêm...'. "
            "Nếu câu hỏi ngoài phạm vi trường hoặc tuyển sinh, hãy trả lời lịch sự rằng hiện mình chỉ hỗ trợ thông tin liên quan đến trường."
        )

        history_text = self._format_history(history)
        context_text = self._format_context(retrieved_chunks)
        prompt = (
            f"Lịch sử hội thoại gần đây:\n{history_text}\n\n"
            f"Thông tin tham chiếu nội bộ:\n{context_text}\n\n"
            f"Intent hien tai: {intent_label}\n"
            f"Huong dan trinh bay: {style_hint}\n"
            f"Câu hỏi hiện tại: {question}\n\n"
            "Hãy trả lời tự nhiên, chính xác, đi thẳng vào nội dung và tuyệt đối không nhắc đến chuyện tham chiếu hay nguồn nội bộ. "
            "Chỉ trả lời phần liên quan trực tiếp đến câu hỏi hiện tại, không thêm câu gợi ý hay lời mời hỏi tiếp ở cuối. "
            "Ưu tiên cách viết dễ đọc trên điện thoại."
        )

        response = self.client.responses.create(
            **self._responses_kwargs(model=self.settings.openai_chat_model),
            instructions=instructions,
            input=prompt,
            max_output_tokens=350,
        )
        return self._normalize_answer(self._extract_text(response))

    def answer_question_with_ptnk_web_search(
        self,
        *,
        question: str,
        history: list[ChatTurn],
        intent_label: str,
    ) -> WebSearchResult:
        search_query = self._build_ptnk_search_query(question, history)
        initial_response = self.client.responses.create(
            **self._responses_kwargs(model=self.settings.openai_web_search_model),
            tools=[self._build_web_search_tool()],
            tool_choice="auto",
            include=["web_search_call.action.sources"],
            instructions=(
                "Bạn là lớp tìm kiếm ngoài web cho chatbot PTNK. "
                "Bắt buộc tìm trên web trước khi trả lời. "
                "Chỉ chấp nhận thông tin nói rõ về đúng Trường Phổ thông Năng khiếu - Đại học Quốc gia TP.HCM. "
                "Không dùng thông tin của các trường khác có chữ 'Năng khiếu'. "
                "Ưu tiên website chính thức của trường, cổng ĐHQG-HCM, hoặc fanpage chính thức của trường. "
                "Nếu câu hỏi không nằm trong phạm vi PTNK hoặc không có đủ nguồn web đáng tin cậy, "
                "hãy trả lời đúng một dòng: NO_WEB_ANSWER. "
                "Nếu trả lời được, chỉ trả về đúng câu trả lời ngắn gọn, tự nhiên, thân thiện với học sinh, mở đầu bằng 'Chào bạn,'. "
                "Không nhắc đến nguồn, tài liệu, dữ liệu hay quá trình tìm kiếm."
            ),
            input=self._build_ptnk_web_search_input(
                question=question,
                history=history,
                intent_label=intent_label,
                search_query=search_query,
            ),
        )

        draft_answer_raw = self._extract_text(initial_response).strip()
        initial_sources = self._filter_ptnk_web_sources(self._extract_web_sources(initial_response))
        if not draft_answer_raw or draft_answer_raw == "NO_WEB_ANSWER" or not initial_sources:
            return WebSearchResult(
                answer="",
                sources=[],
                verified=False,
                search_query=search_query,
            )

        verified_response = self.client.responses.create(
            **self._responses_kwargs(model=self.settings.openai_web_search_model),
            tools=[self._build_web_search_tool()],
            tool_choice="auto",
            include=["web_search_call.action.sources"],
            instructions=(
                "Bạn là lớp kiểm chứng lần 2 cho chatbot PTNK. "
                "Bắt buộc tìm lại trên web trước khi kết luận. "
                "Chỉ xác nhận thông tin về đúng Trường Phổ thông Năng khiếu - Đại học Quốc gia TP.HCM. "
                "Không dùng thông tin của các trường khác có chữ 'Năng khiếu'. "
                "Nếu bản nháp chưa được nguồn web đáng tin cậy xác nhận, hoặc câu hỏi không thuộc PTNK, "
                "hãy trả lời đúng một dòng: NOT_VERIFIED. "
                "Nếu xác nhận được, hãy trả lời đúng định dạng: VERIFIED: <câu trả lời hoàn chỉnh bắt đầu bằng 'Chào bạn,' và có giọng điệu thân thiện, dễ hiểu với học sinh>. "
                "Không thêm giải thích nào ngoài 2 dạng trên."
            ),
            input=self._build_ptnk_verification_input(
                question=question,
                history=history,
                draft_answer=draft_answer_raw,
                search_query=search_query,
            ),
        )

        verified_text_raw = self._extract_text(verified_response).strip()
        verified_sources = self._filter_ptnk_web_sources(self._extract_web_sources(verified_response))
        if not verified_text_raw.startswith("VERIFIED:") or not verified_sources:
            return WebSearchResult(
                answer="",
                sources=verified_sources,
                verified=False,
                search_query=search_query,
            )

        final_answer = verified_text_raw.split("VERIFIED:", 1)[1].strip()
        if not final_answer:
            return WebSearchResult(
                answer="",
                sources=verified_sources,
                verified=False,
                search_query=search_query,
            )

        return WebSearchResult(
            answer=self._normalize_answer(final_answer),
            sources=verified_sources,
            verified=True,
            search_query=search_query,
        )

    def _format_history(self, history: list[ChatTurn]) -> str:
        if not history:
            return "(khong co)"
        recent_turns = history[-6:]
        return "\n".join(f"{turn.role}: {turn.content.strip()}" for turn in recent_turns)

    def _format_context(self, retrieved_chunks: list[RetrievedChunk]) -> str:
        if not retrieved_chunks:
            return "(khong co ngu canh duoc retrieve)"

        sections: list[str] = []
        current_length = 0
        for index, chunk in enumerate(retrieved_chunks, start=1):
            block = (
                f"[{index}] Nguon: {chunk.metadata.get('source_name', 'unknown')} | "
                f"Loai: {chunk.metadata.get('source_type', 'unknown')} | "
                f"Chunk: {chunk.metadata.get('chunk_index', 0)}\n"
                f"{chunk.text.strip()}"
            )
            projected = current_length + len(block)
            if projected > self.settings.max_context_characters and sections:
                break
            sections.append(block)
            current_length = projected
        return "\n\n".join(sections)

    def _build_ptnk_search_query(self, question: str, history: list[ChatTurn]) -> str:
        history_context = " ".join(turn.content.strip() for turn in history[-3:] if turn.role == "user")
        leadership_hint = ""
        normalized_question = self._normalize_for_matching(question)
        if any(
            marker in normalized_question
            for marker in ("hieu truong", "pho hieu truong", "ban giam hieu", "hieu pho", "lanh dao")
        ):
            leadership_hint = " hieu truong pho hieu truong ban giam hieu lanh dao"
        parts = [
            question.strip(),
            history_context.strip(),
            "Truong Pho thong Nang khieu Dai hoc Quoc gia TP.HCM PTNK",
            leadership_hint,
        ]
        return " ".join(part for part in parts if part).strip()

    def _build_ptnk_web_search_input(
        self,
        *,
        question: str,
        history: list[ChatTurn],
        intent_label: str,
        search_query: str,
    ) -> str:
        return (
            f"Câu hỏi của người dùng: {question}\n"
            f"Intent hiện tại: {intent_label}\n"
            f"Lịch sử gần đây: {self._format_history(history)}\n"
            f"Câu truy vấn gợi ý: {search_query}\n\n"
            "Hãy tìm trên web và chỉ trả lời nếu thông tin tìm được là về đúng Trường Phổ thông Năng khiếu - Đại học Quốc gia TP.HCM."
        )

    def _build_ptnk_verification_input(
        self,
        *,
        question: str,
        history: list[ChatTurn],
        draft_answer: str,
        search_query: str,
    ) -> str:
        return (
            f"Câu hỏi của người dùng: {question}\n"
            f"Lịch sử gần đây: {self._format_history(history)}\n"
            f"Bản nháp cần kiểm chứng: {draft_answer}\n"
            f"Câu truy vấn gợi ý: {search_query}\n\n"
            "Hãy tìm lại trên web để xác minh bản nháp. Chỉ xác nhận khi thông tin thật sự thuộc về đúng Trường Phổ thông Năng khiếu - Đại học Quốc gia TP.HCM."
        )

    def _build_web_search_tool(self) -> dict:
        return {
            "type": "web_search",
            "filters": {
                "allowed_domains": list(self.settings.web_search_allowed_domains),
            },
            "user_location": {
                "type": "approximate",
                "country": "VN",
                "city": "Ho Chi Minh City",
                "region": "Ho Chi Minh City",
            },
        }

    @staticmethod
    def _extract_text(response: object) -> str:
        output_text = getattr(response, "output_text", "")
        if output_text:
            return str(output_text)

        output_items = getattr(response, "output", None) or []
        texts: list[str] = []
        for item in output_items:
            item_type = getattr(item, "type", None)
            if item_type is None and isinstance(item, dict):
                item_type = item.get("type")
            if item_type != "message":
                continue
            content_items = getattr(item, "content", None)
            if content_items is None and isinstance(item, dict):
                content_items = item.get("content", [])
            for content in content_items or []:
                text = getattr(content, "text", None)
                if text is None and isinstance(content, dict):
                    text = content.get("text")
                if text:
                    texts.append(str(text))
        return "\n".join(texts)

    def _extract_web_sources(self, response: object) -> list[WebSource]:
        payload = self._response_to_dict(response)
        if not payload:
            return []

        seen_urls: set[str] = set()
        collected: list[WebSource] = []

        def visit(node: object) -> None:
            if isinstance(node, dict):
                url = str(node.get("url", "")).strip()
                if url:
                    title = str(
                        node.get("title")
                        or node.get("site_name")
                        or node.get("name")
                        or node.get("label")
                        or url
                    ).strip()
                    snippet = str(
                        node.get("snippet")
                        or node.get("text")
                        or node.get("description")
                        or node.get("excerpt")
                        or ""
                    ).strip()
                    normalized_url = self._normalize_url(url)
                    if normalized_url and normalized_url not in seen_urls:
                        collected.append(
                            WebSource(
                                title=title,
                                url=normalized_url,
                                snippet=snippet,
                                domain=urlparse(normalized_url).netloc.lower(),
                            )
                        )
                        seen_urls.add(normalized_url)
                for value in node.values():
                    visit(value)
            elif isinstance(node, list):
                for item in node:
                    visit(item)

        visit(payload)
        return collected

    def _filter_ptnk_web_sources(self, sources: list[WebSource]) -> list[WebSource]:
        filtered: list[WebSource] = []
        for source in sources:
            if self._is_ptnk_web_source(source):
                filtered.append(source)
        return filtered

    def _is_ptnk_web_source(self, source: WebSource) -> bool:
        domain = source.domain.lower()
        if not domain:
            return False

        content = " ".join(
            part for part in (source.title, source.snippet, source.url) if part
        ).lower()
        school_markers = (
            "pho thong nang khieu",
            "phổ thông năng khiếu",
            "ptnk",
            "hsgvnuhcm",
        )

        if domain.endswith("ptnk.edu.vn"):
            return True
        if domain.endswith("vnuhcm.edu.vn"):
            return any(marker in content for marker in school_markers)
        if domain.endswith("facebook.com"):
            return any(marker in content for marker in school_markers)
        return any(marker in content for marker in school_markers)

    @staticmethod
    def _normalize_url(url: str) -> str:
        cleaned = url.strip()
        if not cleaned:
            return ""
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            return cleaned
        return f"https://{cleaned}"

    @staticmethod
    def _response_to_dict(response: object) -> dict | list | None:
        if isinstance(response, (dict, list)):
            return response
        if hasattr(response, "model_dump"):
            return response.model_dump()
        if hasattr(response, "to_dict"):
            return response.to_dict()
        return None

    @staticmethod
    def _normalize_for_matching(text: str) -> str:
        lowered = text.lower().replace("đ", "d").replace("Đ", "D")
        normalized = unicodedata.normalize("NFD", lowered)
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return re.sub(r"\s+", " ", normalized).strip()

    def _normalize_answer(self, text: str) -> str:
        answer = text.strip()
        answer = re.sub(
            r"^\s*(theo\s+(tai\s+lieu|du\s+lieu|ngu\s+canh)[^,.:\n]*[,:\-]\s*)",
            "",
            answer,
            flags=re.IGNORECASE,
        )
        answer = re.sub(
            r"^\s*(dua\s+tren\s+tai\s+lieu[^,.:\n]*[,:\-]\s*)",
            "",
            answer,
            flags=re.IGNORECASE,
        )
        substitutions = [
            (
                r"hiện\s+trong\s+tài\s+liệu\s+mình\s+chưa\s+tìm\s+thấy\s+thông\s+tin",
                "hiện mình chưa có thông tin xác nhận",
            ),
            (
                r"trong\s+tài\s+liệu\s+mình\s+chưa\s+tìm\s+thấy\s+thông\s+tin",
                "mình chưa có thông tin xác nhận",
            ),
            (
                r"tài\s+liệu\s+chỉ\s+có",
                "",
            ),
            (
                r"trong\s+tài\s+liệu",
                "",
            ),
            (
                r"theo\s+tài\s+liệu",
                "",
            ),
            (
                r"theo\s+dữ\s+liệu",
                "",
            ),
            (
                r"theo\s+nguồn",
                "",
            ),
        ]
        for pattern, replacement in substitutions:
            answer = re.sub(pattern, replacement, answer, flags=re.IGNORECASE)
        answer = self._remove_unwanted_closing(answer)
        answer = re.sub(r"[ \t]{2,}", " ", answer)
        answer = re.sub(r" ,", ",", answer)
        answer = re.sub(r"\n{3,}", "\n\n", answer)
        answer = re.sub(r"(?<!^)\bChào bạn,\s*", "", answer, flags=re.IGNORECASE)
        answer = re.sub(r"(?<!^)\bChao ban,\s*", "", answer, flags=re.IGNORECASE)
        answer = answer.strip()
        if not answer:
            return "Chào bạn,\n\nHiện mình chưa thể tạo câu trả lời phù hợp."
        if answer.lower().startswith("chào bạn"):
            return self._finalize_answer(answer)
        if answer.lower().startswith("chao ban"):
            normalized = re.sub(r"^chao ban", "Chào bạn", answer, flags=re.IGNORECASE)
            if not normalized.startswith("Chào bạn,"):
                normalized = normalized.replace("Chào bạn", "Chào bạn,", 1)
            return self._finalize_answer(normalized)
        return self._finalize_answer(f"Chào bạn,\n\n{answer}")

    def _remove_unwanted_closing(self, answer: str) -> str:
        normalized = answer.lower()
        if "hiện mình chưa có thông tin xác nhận" in normalized:
            return answer

        closing_starters = (
            "nếu bạn muốn",
            "neu ban muon",
            "nếu bạn cần",
            "neu ban can",
            "mình có thể gửi thêm",
            "minh co the gui them",
            "mình có thể hỗ trợ thêm",
            "minh co the ho tro them",
        )
        lines = [line.strip() for line in answer.splitlines()]
        filtered_lines: list[str] = []
        for line in lines:
            if not line:
                filtered_lines.append("")
                continue
            lowered = line.lower()
            if any(lowered.startswith(starter) for starter in closing_starters):
                continue
            filtered_lines.append(line)

        cleaned = "\n".join(filtered_lines).strip()
        sentence_cut_patterns = (
            r"\n?\s*Nếu bạn muốn[^.!?]*[.!?]?",
            r"\n?\s*Neu ban muon[^.!?]*[.!?]?",
            r"\n?\s*Nếu bạn cần[^.!?]*[.!?]?",
            r"\n?\s*Neu ban can[^.!?]*[.!?]?",
            r"\n?\s*Mình có thể gửi thêm[^.!?]*[.!?]?",
            r"\n?\s*Minh co the gui them[^.!?]*[.!?]?",
        )
        for pattern in sentence_cut_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def _ensure_greeting_layout(self, answer: str) -> str:
        normalized = answer.strip()
        if normalized.startswith("Chào bạn,"):
            body = normalized[len("Chào bạn,"):].strip()
            if not body:
                return "Chào bạn,"
            return f"Chào bạn,\n\n{body}"
        return normalized

    def _finalize_answer(self, answer: str) -> str:
        return self._capitalize_line_starts(self._ensure_greeting_layout(answer))

    def _capitalize_line_starts(self, answer: str) -> str:
        lines = answer.splitlines()
        normalized_lines: list[str] = []
        for line in lines:
            if not line.strip():
                normalized_lines.append("")
                continue
            normalized_lines.append(
                re.sub(
                    r"^(\s*(?:[-*•]\s*|\d+[.)]\s*)?(?:[\"'“‘(\[]\s*)*)([a-zà-ỹđ])",
                    lambda match: f"{match.group(1)}{match.group(2).upper()}",
                    line,
                )
            )
        return "\n".join(normalized_lines)
