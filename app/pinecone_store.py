from __future__ import annotations

import time
from typing import Any

from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions.exceptions import NotFoundException

from .config import Settings
from .types import Chunk, RetrievedChunk


def _safe_get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    if hasattr(obj, name):
        return getattr(obj, name)
    try:
        return obj[name]
    except Exception:
        return default


def _to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:
            return {}
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            return {}
    return {}


class PineconeVectorStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = Pinecone(api_key=settings.pinecone_api_key)

    def upsert_chunks(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
        *,
        reset_namespace: bool = False,
    ) -> int:
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError("Chunks and embeddings must have the same length")

        self.ensure_index(dimension=len(embeddings[0]))
        index = self._get_index()

        if reset_namespace:
            self._reset_namespace(index)
            time.sleep(1)

        batch_size = 100
        for start in range(0, len(chunks), batch_size):
            batch_chunks = chunks[start : start + batch_size]
            batch_embeddings = embeddings[start : start + batch_size]
            vectors = [
                {
                    "id": chunk.id,
                    "values": embedding,
                    "metadata": {
                        **chunk.metadata,
                        "text": chunk.text,
                    },
                }
                for chunk, embedding in zip(batch_chunks, batch_embeddings, strict=True)
            ]
            index.upsert(vectors=vectors, namespace=self.settings.pinecone_namespace)

        return len(chunks)

    def query(self, vector: list[float], top_k: int) -> list[RetrievedChunk]:
        if not self.index_exists():
            raise ValueError(
                "Pinecone index chua ton tai. Hay goi /ingest truoc khi chat."
            )

        index = self._get_index()
        response = index.query(
            vector=vector,
            top_k=top_k,
            namespace=self.settings.pinecone_namespace,
            include_metadata=True,
        )
        matches = _safe_get(response, "matches", []) or []

        results: list[RetrievedChunk] = []
        for match in matches:
            metadata = _to_dict(_safe_get(match, "metadata", {}))
            text = str(metadata.pop("text", "")).strip()
            results.append(
                RetrievedChunk(
                    id=str(_safe_get(match, "id", "")),
                    text=text,
                    score=float(_safe_get(match, "score", 0.0) or 0.0),
                    metadata=metadata,
                )
            )
        return results

    def ensure_index(self, dimension: int) -> None:
        if not self.index_exists():
            self.client.create_index(
                name=self.settings.pinecone_index_name,
                dimension=dimension,
                metric=self.settings.pinecone_metric,
                spec=ServerlessSpec(
                    cloud=self.settings.pinecone_cloud,
                    region=self.settings.pinecone_region,
                ),
            )

        description = self.client.describe_index(name=self.settings.pinecone_index_name)
        current_dimension = int(_safe_get(description, "dimension", 0) or 0)
        if current_dimension and current_dimension != dimension:
            raise ValueError(
                "Dimension cua Pinecone index khong trung voi embedding model hien tai. "
                "Hay doi index name moi hoac reset index."
            )

        for _ in range(60):
            description = self.client.describe_index(name=self.settings.pinecone_index_name)
            status = _safe_get(description, "status", {}) or {}
            ready = bool(_safe_get(status, "ready", False))
            if ready:
                return
            time.sleep(2)

        raise TimeoutError("Pinecone index khong san sang sau 120 giay")

    def index_exists(self) -> bool:
        listed = self.client.list_indexes()

        if hasattr(listed, "names"):
            try:
                return self.settings.pinecone_index_name in set(listed.names())
            except Exception:
                pass

        if isinstance(listed, dict):
            indexes = listed.get("indexes", listed)
        else:
            indexes = listed

        names: set[str] = set()
        for item in indexes:
            if isinstance(item, str):
                names.add(item)
            else:
                name = _safe_get(item, "name")
                if name:
                    names.add(str(name))
        return self.settings.pinecone_index_name in names

    def _get_index(self) -> Any:
        description = self.client.describe_index(name=self.settings.pinecone_index_name)
        host = _safe_get(description, "host")
        if host:
            return self.client.Index(host=host)
        return self.client.Index(self.settings.pinecone_index_name)

    def _reset_namespace(self, index: Any) -> None:
        try:
            index.delete(delete_all=True, namespace=self.settings.pinecone_namespace)
        except NotFoundException:
            # Pinecone may return 404 when the namespace has not been created yet.
            return
