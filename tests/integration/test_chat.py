import pytest
from fastapi.testclient import TestClient

from semantic_search_middleware.api.dependencies import get_chat_service
from semantic_search_middleware.api.main import app
from semantic_search_middleware.domain.errors import LlmError
from semantic_search_middleware.domain.models import ChatAnswer, Citation


class FakeChatService:
    def __init__(self, result):
        self._result = result

    def answer(self, message):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_chat_returns_answer_and_citations() -> None:
    answer = ChatAnswer(
        answer="SMTP was rate-limiting.",
        citations=[Citation(table="support_tickets", primary_key="id", primary_key_value="42")],
        supported=True,
    )
    app.dependency_overrides[get_chat_service] = lambda: FakeChatService(answer)

    response = TestClient(app).post("/api/v1/chat", json={"message": "why did the reset fail?"})

    body = response.json()
    assert response.status_code == 200
    assert body["answer"] == "SMTP was rate-limiting."
    assert body["supported"] is True
    assert body["citations"][0]["primary_key_value"] == "42"
    assert body["conversation_id"]


def test_chat_echoes_the_supplied_conversation_id() -> None:
    answer = ChatAnswer(answer="…", citations=[], supported=False)
    app.dependency_overrides[get_chat_service] = lambda: FakeChatService(answer)

    response = TestClient(app).post(
        "/api/v1/chat", json={"message": "hello", "conversation_id": "abc-123"}
    )

    assert response.json()["conversation_id"] == "abc-123"


def test_chat_returns_503_when_the_model_is_unreachable() -> None:
    app.dependency_overrides[get_chat_service] = lambda: FakeChatService(LlmError("down"))

    response = TestClient(app).post("/api/v1/chat", json={"message": "why did the reset fail?"})

    # Never degrade to an ungrounded or empty answer — fail visibly.
    assert response.status_code == 503
