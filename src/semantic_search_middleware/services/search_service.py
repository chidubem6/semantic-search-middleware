from typing import Any

from semantic_search_middleware.domain.models import SearchResult
from semantic_search_middleware.domain.ports import Embedder, VectorStore


class SearchService:
    def __init__(self, embedder: Embedder, vector_store: VectorStore) -> None:
        self._embedder = embedder
        self._vector_store = vector_store

    def search(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        query_vector = self._embedder.embed([query])[0]
        return self._vector_store.search(query_vector, top_k=top_k, filters=filters)
