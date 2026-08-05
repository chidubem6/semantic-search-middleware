from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from semantic_search_middleware.api.dependencies import get_chat_service
from semantic_search_middleware.api.schemas import ChatRequest, ChatResponse
from semantic_search_middleware.domain.errors import LlmError
from semantic_search_middleware.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    try:
        response = service.answer(request.message)

        return ChatResponse(
            answer=response.answer,
            citations=response.citations,
            conversation_id=request.conversation_id or str(uuid4()),
            supported=response.supported,
        )
    except LlmError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
