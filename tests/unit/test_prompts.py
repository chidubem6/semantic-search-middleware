from semantic_search_middleware.domain.models import (
    IndexedDocument,
    SearchResult,
    SourceReference,
)
from semantic_search_middleware.rag.prompts import build_context_prompt


def make_result(pk_value, text, score):
    return SearchResult(
        document=IndexedDocument(
            document_id=f"support_tickets:{pk_value}",
            text=text,
            source=SourceReference(
                table="support_tickets", primary_key="id", primary_key_value=pk_value
            ),
        ),
        score=score,
    )


RESULTS = [
    make_result("42", "Record from support_tickets. subject: password reset fails.", 0.91),
    make_result("88", "Record from support_tickets. subject: reset link expired.", 0.72),
]

QUESTION = "how do I fix a failed password reset?"


def test_prompt_contains_the_question() -> None:
    prompt = build_context_prompt(QUESTION, RESULTS)

    assert QUESTION in prompt


def test_prompt_contains_every_row_and_its_source_labels() -> None:
    prompt = build_context_prompt(QUESTION, RESULTS)

    for result in RESULTS:
        assert result.document.text in prompt
        assert result.document.source.table in prompt
        assert result.document.source.primary_key_value in prompt


def test_prompt_is_deterministic() -> None:
    assert build_context_prompt(QUESTION, RESULTS) == build_context_prompt(QUESTION, RESULTS)
