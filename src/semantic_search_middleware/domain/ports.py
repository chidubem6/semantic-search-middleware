"""Port definitions for the middleware's external dependencies.

Structural (`Protocol`) interfaces for the relational connector, embedder,
vector store and LLM client. As the domain layer's outward-facing ports, they
let services depend on behaviour rather than concrete adapters, keeping the
dependency arrows pointing inward.
"""

from collections.abc import Iterable, Sequence
from typing import Any, Protocol

from .models import IndexedDocument, SearchResult


class RelationalConnector(Protocol):
    def read_rows(self, table: str, columns: Sequence[str]) -> Iterable[dict[str, Any]]: ...

    def read_referenced_rows(
        self, table: str, key: str, key_values: Iterable[Any], columns: Sequence[str]
    ) -> dict[Any, dict[str, Any]]: ...


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


class LlmClient(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str: ...
