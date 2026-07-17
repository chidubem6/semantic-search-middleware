from fastapi import APIRouter

from semantic_search_middleware.api.schemas import SearchRequest, SearchResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    # TODO: inject SearchService and replace the placeholder.
    return SearchResponse(query=request.query, results=[])
