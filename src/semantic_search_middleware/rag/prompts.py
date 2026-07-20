from collections.abc import Sequence

from semantic_search_middleware.domain.models import SearchResult

GROUNDED_SYSTEM_PROMPT = """
You answer questions using only the supplied database records.

Rules:
1. Do not use outside knowledge.
2. If the records are insufficient, say that there is not enough information.
3. Every factual claim must be supported by at least one source-row citation.
4. Never invent table names, primary keys, values, or citations.
""".strip()


# The user-facing prompt: labelled context rows (best-first), then the question.
def build_context_prompt(question: str, results: Sequence[SearchResult]) -> str:
    lines = []

    for result in results:
        lines.append(f"[{result.document.document_id}] {result.document.text}")

    context = "\n".join(lines)

    return f"{context}\n\nQuestion: {question}"


INSUFFICIENT_CONTEXT_ANSWER = (
    "I could not find any records relevant to that question, so I cannot answer it."
)
