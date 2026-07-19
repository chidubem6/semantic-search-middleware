from functools import lru_cache

from semantic_search_middleware.config.settings import get_settings
from semantic_search_middleware.embeddings.sentence_transformer import SentenceTransformerEmbedder
from semantic_search_middleware.services.search_service import SearchService
from semantic_search_middleware.vectorstores.pgvector_store import PgVectorStore


@lru_cache
def get_search_service() -> SearchService:
    settings = get_settings()
    return SearchService(
        SentenceTransformerEmbedder(settings.embedding_model),
        PgVectorStore(
            settings.database_url, settings.embedding_dimension, settings.min_similarity_score
        ),
    )
