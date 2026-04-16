from __future__ import annotations

import hashlib
import re

from .types import Chunk, RawDocument


class TextChunker:
    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be >= 0")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_documents(self, documents: list[RawDocument]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for document in documents:
            chunks.extend(self.chunk_document(document))
        return chunks

    def chunk_document(self, document: RawDocument) -> list[Chunk]:
        pieces = self._split_text(document.text)
        chunks: list[Chunk] = []
        for chunk_index, piece in enumerate(pieces):
            stable_key = f"{document.source_id}:{chunk_index}"
            chunk_id = hashlib.sha1(stable_key.encode("utf-8")).hexdigest()
            metadata = {
                **document.metadata,
                "source_id": document.source_id,
                "source_name": document.source_name,
                "source_type": document.source_type,
                "chunk_index": chunk_index,
            }
            chunks.append(Chunk(id=chunk_id, text=piece, metadata=metadata))
        return chunks

    def _split_text(self, text: str) -> list[str]:
        normalized = re.sub(r"\n{3,}", "\n\n", text).strip()
        if not normalized:
            return []
        if len(normalized) <= self.chunk_size:
            return [normalized]

        chunks: list[str] = []
        start = 0
        text_length = len(normalized)
        target_floor = self.chunk_size // 2

        while start < text_length:
            max_end = min(text_length, start + self.chunk_size)
            end = max_end

            if max_end < text_length:
                candidate_positions = [
                    normalized.rfind("\n\n", start + target_floor, max_end),
                    normalized.rfind("\n", start + target_floor, max_end),
                    normalized.rfind(" ", start + target_floor, max_end),
                ]
                best = max(candidate_positions)
                if best > start:
                    end = best

            piece = normalized[start:end].strip()
            if piece:
                chunks.append(piece)

            if end >= text_length:
                break

            next_start = max(0, end - self.chunk_overlap)
            if next_start <= start:
                next_start = end
            start = next_start

        return chunks

