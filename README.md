# Semantic Search Middleware

A read-only middleware that indexes relational database records as embeddings and exposes semantic search and grounded chat APIs.

## MVP stack

- Python 3.12
- FastAPI
- PostgreSQL + pgvector
- SQLAlchemy 2
- sentence-transformers
- Streamlit
- pytest

## Architecture

```text
PostgreSQL -> Connector -> Verbaliser -> Embedder -> pgvector
                                                   |
User -> Streamlit -> FastAPI -> Retriever ---------+
                         |
                         +-> RAG service -> grounded answer + row citations
```

## Repository layout

```text
src/semantic_search_middleware/
├── api/            # FastAPI app and HTTP routes
├── config/         # Environment/config loading
├── connectors/     # Relational database access
├── domain/         # Core models and interfaces
├── embeddings/     # Embedding provider implementations
├── ingestion/      # Row verbalisation and indexing pipeline
├── rag/            # Grounded answer generation
├── retrieval/      # Semantic and hybrid retrieval
├── services/       # Application use cases
└── vectorstores/   # pgvector implementation
```

## First-time setup

```bash
cp .env.example .env
docker compose up -d db
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e '.[dev]'
uvicorn semantic_search_middleware.api.main:app --reload
```

Open `http://localhost:8000/docs`.

## Initial endpoints

- `GET /health`
- `POST /api/v1/search`
- `POST /api/v1/chat`

The search and chat endpoints currently expose the intended contracts and return placeholder results until the indexing and retrieval implementations are completed.

## Recommended build order

1. Load configuration and connect to PostgreSQL.
2. Read one table and preserve table name + primary key.
3. Verbalise each row deterministically.
4. Embed and save documents in pgvector.
5. Implement vector search with citations.
6. Add grounded chat generation.
7. Add hybrid lexical/vector retrieval.
8. Build the evaluation dataset before adding advanced features.

See [`docs/ROADMAP.md`](docs/ROADMAP.md) and [`docs/architecture.md`](docs/architecture.md).
