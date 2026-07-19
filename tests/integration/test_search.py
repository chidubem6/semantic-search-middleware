from fastapi.testclient import TestClient

from semantic_search_middleware.api.dependencies import get_search_service
from semantic_search_middleware.api.main import app
from semantic_search_middleware.domain.models import IndexedDocument, SearchResult, SourceReference


class FakeSearchService:
    def search(self, query, top_k, filters=None):
        return [
            SearchResult(
                document=IndexedDocument(
                    document_id="42",
                    text="Help",
                    source=SourceReference(
                        table="support_tickets", primary_key="id", primary_key_value="42"
                    ),
                ),
                score=0.9,
            )
        ]


def test_search_returns_results() -> None:
    app.dependency_overrides[get_search_service] = lambda: FakeSearchService()

    response = TestClient(app).post("/api/v1/search", json={"query": "payment problem"})

    body = response.json()
    assert body["results"][0]["document"]["source"]["primary_key_value"] == "42"

    app.dependency_overrides.clear()
