from semantic_search_middleware.ingestion.indexer import IndexingService
from semantic_search_middleware.ingestion.verbaliser import RowVerbaliser


# Could be MySQL, or another database entirely. Swapping it is what lets this
# middleware be "universal" — the service only depends on the port, not on Postgres.
class FakeConnector:
    def read_rows(self, table, columns):
        return [
            {"id": 1, "subject": "login broken"},
            {"id": 2, "subject": "payment failed"},
        ]


class FakeEmbedder:  # Diffferent embedders exist
    def embed(self, texts):
        return [[0.1] * 384 for _ in texts]


class FakeStore:
    def __init__(self):
        self.upserted = []

    def upsert(self, documents, vectors):
        self.upserted = documents  # record what it was given

    def search(self, query_vector, top_k, filters=None):
        return []


def test_indexer() -> None:
    store = FakeStore()
    indexer = IndexingService(FakeConnector(), RowVerbaliser(), FakeEmbedder(), store)

    count = indexer.index_table("support_tickets", "id", ["subject"])

    assert count == 2
    assert store.upserted[0].document_id == "support_tickets:1"
    assert "id: 1" not in store.upserted[0].text
    assert store.upserted[0].source.primary_key_value == "1"
