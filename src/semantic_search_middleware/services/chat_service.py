from semantic_search_middleware.domain.models import ChatAnswer, Citation
from semantic_search_middleware.domain.ports import LlmClient
from semantic_search_middleware.rag.prompts import GROUNDED_SYSTEM_PROMPT, build_context_prompt
from semantic_search_middleware.services.search_service import SearchService

INSUFFICIENT_CONTEXT_ANSWER = (
    "I could not find any records relevant to that question, so I cannot answer it."
)


class ChatService:
    """Answers a question from retrieved rows, or abstains when nothing is found."""

    def __init__(self, search_service: SearchService, llm: LlmClient, top_k: int) -> None:
        self._search_service = search_service
        self._llm = llm
        self._top_k = top_k

    def answer(self, message: str) -> ChatAnswer:
        results = self._search_service.search(message, self._top_k)

        # Nothing relevant was retrieved: refuse without paying for an LLM call.
        if not results:
            return ChatAnswer(answer=INSUFFICIENT_CONTEXT_ANSWER, citations=[], supported=False)

        user_prompt = build_context_prompt(question=message, results=results)

        citations = [
            Citation(
                table=result.document.source.table,
                primary_key=result.document.source.primary_key,
                primary_key_value=result.document.source.primary_key_value,
            )
            for result in results
        ]

        return ChatAnswer(
            answer=self._llm.complete(GROUNDED_SYSTEM_PROMPT, user_prompt),
            citations=citations,
            supported=True,
        )
