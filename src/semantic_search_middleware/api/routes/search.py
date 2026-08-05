"""Semantic search route.

Handles ``POST /search`` by delegating the query to the injected
``SearchService`` and returning scored results. This is the API (driving)
adapter over the retrieval stage of the pipeline.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from semantic_search_middleware.api.dependencies import get_search_service
from semantic_search_middleware.api.schemas import SearchRequest, SearchResponse
from semantic_search_middleware.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search(
    request: SearchRequest,
    service: Annotated[SearchService, Depends(get_search_service)],
) -> SearchResponse:
    results = service.search(request.query, request.top_k)
    return SearchResponse(query=request.query, results=results)
