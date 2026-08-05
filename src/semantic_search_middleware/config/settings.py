from functools import lru_cache
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Relationship(BaseModel):
    local_column: str
    referenced_table: str
    referenced_key: str
    columns: list[str]
    label: str


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
    # values get verbalised into the text we embed.
    index_table: str = "support_tickets"
    index_primary_key: str = "id"
    index_columns: list[str] = ["subject", "body", "product", "status", "priority"]
    index_strategy: Literal["isolated", "joined"] = "isolated"
    index_relationships: list[Relationship] = [
        Relationship(
            local_column="customer_id",
            referenced_table="customers",
            referenced_key="id",
            columns=["name", "plan", "region"],
            label="customer",
        ),
        Relationship(
            local_column="product_id",
            referenced_table="products",
            referenced_key="id",
            columns=["team"],
            # The ticket's own "product" column already carries the name, so this
            # relationship adds only what an isolated row cannot reach: the team.
            label="product team",
        ),
    ]
    llm_provider: str = "ollama"
    llm_model: str = "llama3.2"
    ollama_base_url: str = "http://localhost:11434"
    llm_timeout_seconds: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
