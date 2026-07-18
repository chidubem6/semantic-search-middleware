from collections.abc import Iterable, Sequence
from typing import Any, Protocol

from .models import IndexedDocument, SearchResult


class RelationalConnector(Protocol):
    def read_rows(self, table: str, columns: Sequence[str]) -> Iterable[dict[str, Any]]: ...


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class VectorStore(Protocol):
    def upsert(
        self, documents: Sequence[IndexedDocument], vectors: Sequence[list[float]]
    ) -> None: ...

    def search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]: ...
