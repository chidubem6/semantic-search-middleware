from semantic_search_middleware.config import get_settings
from semantic_search_middleware.connectors.postgres import PostgresConnector
from semantic_search_middleware.embeddings.sentence_transformer import SentenceTransformerEmbedder
from semantic_search_middleware.ingestion.indexer import IndexingService
from semantic_search_middleware.ingestion.verbaliser import RowVerbaliser
from semantic_search_middleware.vectorstores.pgvector_store import PgVectorStore


def main() -> None:
    settings = get_settings()

    service = IndexingService(
        PostgresConnector(settings.source_database_url),  # reads the SOURCE db
        RowVerbaliser(),
        SentenceTransformerEmbedder(settings.embedding_model),
        PgVectorStore(settings.database_url, settings.embedding_dimension),  # writes YOUR db
    )

    count = service.index_table(
        settings.index_table, settings.index_primary_key, settings.index_columns
    )
    print(f"Indexed {count} documents from {settings.index_table}")


if __name__ == "__main__":
    main()
