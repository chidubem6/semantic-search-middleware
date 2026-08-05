"""Tests IndexingService with the isolated strategy.

Asserts it reads only the row's own columns, so a table without the relationship
local columns can still be indexed while relationships remain configured.
"""

from collections.abc import Iterable, Sequence
from typing import Any

from semantic_search_middleware.config.settings import Relationship
from semantic_search_middleware.domain.models import IndexedDocument
from semantic_search_middleware.ingestion.indexer import IndexingService
from semantic_search_middleware.ingestion.verbaliser import RowVerbaliser


class StrictFakeConnector:
    """A table with no foreign-key columns, which rejects anything it lacks.

    PostgresConnector resolves each requested column against the reflected table
    and raises when one is missing, so asking for a column that does not exist is
    an error rather than something quietly ignored.
    """

    columns_available = frozenset({"id", "subject"})

    def read_rows(self, table: str, columns: Sequence[str]) -> list[dict[str, Any]]:
        missing = [column for column in columns if column not in self.columns_available]
        if missing:
            raise KeyError(f"no such column(s) in {table}: {missing}")

        return [{"id": 1, "subject": "login broken"}]

    def read_referenced_rows(
        self, table: str, key: str, key_values: Iterable[Any], columns: Sequence[str]
    ) -> dict[Any, dict[str, Any]]:
        raise AssertionError("the isolated strategy must not resolve relationships")


class CapturingEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] | None = None

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.texts = list(texts)
        return [[0.0] for _ in texts]


class NullStore:
    def upsert(self, documents: Sequence[IndexedDocument], vectors: Sequence[list[float]]) -> None:
        pass


def test_isolated_strategy_does_not_read_relationship_columns() -> None:
    embedder = CapturingEmbedder()
    service = IndexingService(StrictFakeConnector(), RowVerbaliser(), embedder, NullStore())
    rel = Relationship(
        local_column="customer_id",
        referenced_table="customers",
        referenced_key="id",
        columns=["name", "plan", "region"],
        label="customer",
    )

    # Relationships stay configured -- the strategy alone decides whether they are
    # used, and index_source.py always passes them.
    indexed = service.index_table(
        "support_tickets", "id", ["subject"], relationships=[rel], strategy="isolated"
    )

    assert indexed == 1
    assert embedder.texts is not None
    assert "customer" not in embedder.texts[0]
