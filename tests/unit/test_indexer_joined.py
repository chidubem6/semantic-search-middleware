"""Tests IndexingService with the joined strategy.

Asserts related-table fields are folded into the embedded text of each base row.
"""

from semantic_search_middleware.config.settings import Relationship
from semantic_search_middleware.ingestion.indexer import IndexingService
from semantic_search_middleware.ingestion.verbaliser import RowVerbaliser


class FakeConnector:
    def read_rows(self, table, columns):
        return [{"id": 1, "subject": "login broken", "customer_id": 7}]

    def read_referenced_rows(self, table, key, key_values, columns):
        assert list(key_values) == [7]  # batch-resolved from the base rows
        return {7: {"name": "Ada", "plan": "enterprise", "region": "EU"}}


class CapturingEmbedder:
    def __init__(self):
        self.texts = None

    def embed(self, texts):
        self.texts = list(texts)
        return [[0.0] for _ in texts]


class NullStore:
    def upsert(self, documents, vectors):
        pass


def test_joined_strategy_embeds_text_containing_related_fields():
    embedder = CapturingEmbedder()
    service = IndexingService(FakeConnector(), RowVerbaliser(), embedder, NullStore())
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
