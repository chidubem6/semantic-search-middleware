"""Tests ChatService.

Asserts it abstains without calling the LLM when retrieval is empty; otherwise
passes the question and configured top_k to retrieval, sends a grounded prompt,
and cites every retrieved row.
"""

from typing import Any

from semantic_search_middleware.domain.models import (
    IndexedDocument,
    SearchResult,
    SourceReference,
)
from semantic_search_middleware.services.chat_service import ChatService


class FakeSearchService:
    def __init__(self, results: list[SearchResult]) -> None:
        self._results = results
        self.calls: list[tuple[str, int]] = []

    def search(
        self, query: str, top_k: int, filters: dict[str, Any] | None = None
    ) -> list[SearchResult]:
        self.calls.append((query, top_k))
        return self._results


class RecordingLlm:
    def __init__(self, reply: str = "The reset failed because SMTP was rate-limiting.") -> None:
        self._reply = reply
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self._reply


def make_result(pk_value: str, score: float) -> SearchResult:
    return SearchResult(
        document=IndexedDocument(
            document_id=f"support_tickets:{pk_value}",
            text=f"Record from support_tickets. subject: ticket {pk_value}.",
            source=SourceReference(
                table="support_tickets", primary_key="id", primary_key_value=pk_value
            ),
        ),
        score=score,
    )


def test_abstains_without_calling_the_llm_when_retrieval_is_empty() -> None:
    llm = RecordingLlm()
    service = ChatService(FakeSearchService([]), llm, top_k=5)

    result = service.answer("what is the capital of France?")

    assert result.supported is False
    assert result.citations == []
    # The point of this test: refusing must be free. If this ever fails we are
    # paying a model to answer questions we already know we cannot ground.
    assert llm.calls == []


def test_returns_the_llm_answer_when_rows_are_retrieved() -> None:
    llm = RecordingLlm(reply="SMTP was rate-limiting.")
    service = ChatService(FakeSearchService([make_result("42", 0.9)]), llm, top_k=5)

    result = service.answer("why did the reset fail?")

    assert result.supported is True
    assert result.answer == "SMTP was rate-limiting."
    assert len(llm.calls) == 1


def test_cites_every_retrieved_row() -> None:
    results = [make_result("42", 0.9), make_result("88", 0.7)]
    service = ChatService(FakeSearchService(results), RecordingLlm(), top_k=5)

    result = service.answer("why did the reset fail?")

    assert [c.primary_key_value for c in result.citations] == ["42", "88"]
    assert result.citations[0].table == "support_tickets"


def test_passes_the_question_and_configured_top_k_to_retrieval() -> None:
    search = FakeSearchService([make_result("42", 0.9)])
    service = ChatService(search, RecordingLlm(), top_k=3)

    service.answer("why did the reset fail?")

    assert search.calls == [("why did the reset fail?", 3)]


def test_sends_the_grounded_system_prompt_and_a_context_prompt() -> None:
    llm = RecordingLlm()
    service = ChatService(FakeSearchService([make_result("42", 0.9)]), llm, top_k=5)

    service.answer("why did the reset fail?")

    system_prompt, user_prompt = llm.calls[0]
    assert "only the supplied database records" in system_prompt
    assert "why did the reset fail?" in user_prompt
    assert "42" in user_prompt
