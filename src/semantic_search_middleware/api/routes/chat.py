from uuid import uuid4

from fastapi import APIRouter

from semantic_search_middleware.api.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    # TODO: retrieve context, call the configured LLM, and run a faithfulness check.
    return ChatResponse(
        answer="Not enough information has been indexed to answer this question.",
        citations=[],
        conversation_id=request.conversation_id or str(uuid4()),
        supported=False,
    )
