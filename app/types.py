from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RawDocument:
    source_id: str
    source_name: str
    source_type: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WebSource:
    title: str
    url: str
    snippet: str = ""
    domain: str = ""


@dataclass(frozen=True)
class WebSearchResult:
    answer: str
    sources: list[WebSource] = field(default_factory=list)
    verified: bool = False
    search_query: str = ""
