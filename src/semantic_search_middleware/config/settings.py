from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": the .env file is shared with Docker (e.g. DB_PORT), so
    # ignore env vars that aren't settings fields instead of erroring on them.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_name: str = "Semantic Search Middleware"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/semantic_search"
    source_database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/source_data"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    top_k: int = 5
    min_similarity_score: float = 0.30
    # Which source table to index, its primary-key column, and the columns whose
    # values get verbalized into the text we embed.
    index_table: str = "support_tickets"
    index_primary_key: str = "id"
    index_columns: list[str] = ["subject", "body", "product", "status", "priority"]
    llm_provider: str = "ollama"
    llm_model: str = "llama3.2"
    ollama_base_url: str = "http://localhost:11434"


@lru_cache
def get_settings() -> Settings:
    return Settings()
