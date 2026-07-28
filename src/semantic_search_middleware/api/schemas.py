"""Pydantic request and response schemas for the HTTP API.

Defines the validated wire contracts for the search and chat endpoints,
wrapping domain models such as ``SearchResult`` and ``Citation``. Lives in the
API (driving) adapter as the boundary between HTTP and the service layer.
"""

from typing import Any

from pydantic import BaseModel, Field

from semantic_search_middleware.domain.models import Citation, SearchResult


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    filters: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    conversation_id: str
    supported: bool
