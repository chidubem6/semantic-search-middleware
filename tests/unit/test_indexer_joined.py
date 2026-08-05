"""Tests IndexingService with the joined strategy.

Asserts related-table fields are folded into the embedded text of each base row,
that the referenced key is not, and that referenced rows are fetched in one
batched call rather than one per row.
"""

from collections.abc import Iterable, Sequence
from typing import Any

from semantic_search_middleware.config.settings import Relationship
from semantic_search_middleware.domain.models import IndexedDocument
from semantic_search_middleware.ingestion.indexer import IndexingService
from semantic_search_middleware.ingestion.verbaliser import RowVerbaliser


class FakeConnector:
    """Two tickets sharing one customer, so batching is actually observable."""

    def __init__(self) -> None:
        # Spy: every call's key_values, so the test can assert how it was called.
        self.referenced_calls: list[list[Any]] = []

    def read_rows(self, table: str, columns: Sequence[str]) -> list[dict[str, Any]]:
        return [
            {"id": 1, "subject": "login broken", "customer_id": 90210},
            {"id": 2, "subject": "export fails", "customer_id": 90210},
        ]

    def read_referenced_rows(
        self, table: str, key: str, key_values: Iterable[Any], columns: Sequence[str]
    ) -> dict[Any, dict[str, Any]]:
        self.referenced_calls.append(list(key_values))
        # Mirrors PostgresConnector: its SELECT puts the key column first, so the
        # key comes back inside each row even though it was not in `columns`.
        return {90210: {"id": 90210, "name": "Ada", "plan": "enterprise", "region": "EU"}}


class CapturingEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] | None = None

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.texts = list(texts)
        return [[0.0] for _ in texts]


class NullStore:
    def upsert(self, documents: Sequence[IndexedDocument], vectors: Sequence[list[float]]) -> None:
        pass


def test_joined_strategy_embeds_text_containing_related_fields() -> None:
    connector = FakeConnector()  # named: the test inspects its recorded calls below
    embedder = CapturingEmbedder()
    service = IndexingService(connector, RowVerbaliser(), embedder, NullStore())
    rel = Relationship(
        local_column="customer_id",
        referenced_table="customers",
        referenced_key="id",
        columns=["name", "plan", "region"],
        label="customer",
    )

    service.index_table(
        "support_tickets", "id", ["subject"], relationships=[rel], strategy="joined"
    )

    assert "enterprise" in embedder.texts[0]  # only reachable via the join
    assert "Ada" in embedder.texts[0]

    # The join key is an accident of storage, not meaning -- it must not reach the
    # embedded text, even though the connector returns it.
    assert "90210" not in embedder.texts[0], embedder.texts[0]

    # ONE batched call carrying both rows' keys -- not one call per row (N+1).
    assert connector.referenced_calls == [[90210, 90210]]
