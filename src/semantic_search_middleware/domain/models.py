"""Core domain models shared across the middleware.

Pydantic value objects that flow through the pipeline — from a source-row
reference and the indexed document embedded in pgvector, to scored search
results and grounded chat answers with citations. These are the domain layer's
data contracts, depended on by every adapter and service.
"""

from typing import Any

from pydantic import BaseModel, Field


class SourceReference(BaseModel):
    table: str
    primary_key: str
    primary_key_value: str


class IndexedDocument(BaseModel):
    document_id: str
    text: str
    source: SourceReference
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    document: IndexedDocument
    score: float = Field(ge=0.0, le=1.0)


class Citation(BaseModel):
    table: str
    primary_key: str
    primary_key_value: str


class ChatAnswer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    supported: bool
