# Milestone 0 — Vertical Slice Design

**Date:** 2026-07-17
**Status:** Approved (design), pending spec review

## Context

`semantic-search-middleware` is a read-only middleware that indexes relational
database rows as embeddings and serves semantic search (Milestone 0) and, later,
grounded RAG chat. Milestone 0 proves the vertical slice end-to-end: read one
source table → verbalize each row → embed locally → store in pgvector → return
top-k matches from `POST /api/v1/search` with source citations.

This is a tutorial + portfolio project. Per the agreed working model, **Chidubem
writes the instructive core logic** (marked ✍️ CHIDUBEM below) and **Claude
scaffolds the plumbing** (marked 🔧 CLAUDE). Every new concept is explained
before the code.

The scaffolding already implements: `PostgresConnector.read_rows`,
`SentenceTransformerEmbedder.embed`, `RowVerbalizer.verbalize`,
`SearchService.search`, and the domain ports/models (`RelationalConnector`,
`Embedder`, `VectorStore`, `IndexedDocument`, `SearchResult`, `SourceReference`,
`Citation`). The chief gap is the pgvector `VectorStore`, an indexing entrypoint,
sample data, config, and wiring the `/search` route.

## Goals

- Index a synthetic **support-tickets** table (~400 rows) into pgvector.
- `POST /api/v1/search` returns ranked results with similarity scores and
  citations, filtered by `MIN_SIMILARITY_SCORE`.
- Idempotent re-indexing (deterministic document IDs + upsert).
- Tests that keep CI green without a live database.

## Non-goals (later milestones)

- Grounded chat / LLM (`/chat` stays a placeholder) — Milestone 1.
- Foreign-key / relationship-aware verbalisation — Milestone 2.
- Hybrid lexical + vector retrieval — Milestone 3.
- Sync / change detection — Milestone 4.

## Data layout

Two databases in the one Postgres (pgvector) instance, matching existing
settings:

- `source_data` DB → `support_tickets` table (the "someone else's" source DB the
  middleware reads, read-only).
- `semantic_search` DB → `documents` table (our embeddings index).

`docker-compose.yml` + `scripts/init.sql` create both DBs; a committed
`scripts/seed_source.sql` loads ~400 synthetic tickets. 🔧 CLAUDE

**support_tickets columns:** `id` (PK), `subject`, `body`, `product`, `status`,
`priority`, `created_at`. Synthetic, non-sensitive.

## Components

### 1. pgvector VectorStore — `vectorstores/pgvector_store.py`

`documents` table (SQLAlchemy Core `Table`):

| column | type | purpose |
|---|---|---|
| `document_id` | `text` PRIMARY KEY | deterministic `"support_tickets:<id>"` |
| `content` | `text` | verbalized row |
| `embedding` | `Vector(384)` (pgvector) | the embedding |
| `source_table` | `text` | citation |
| `source_pk` | `text` | citation (pk column name) |
| `source_pk_value` | `text` | citation (pk value) |
| `doc_metadata` | `jsonb` | extra fields |

- Table definition + engine setup + `upsert()` (`INSERT ... ON CONFLICT
  (document_id) DO UPDATE`). 🔧 CLAUDE (SQLAlchemy boilerplate)
- `search()` — the instructive part: cosine distance via pgvector `<=>`
  operator, `ORDER BY embedding <=> :q ASC`, `LIMIT top_k`; convert distance →
  similarity as `score = 1 - distance`; drop rows below `MIN_SIMILARITY_SCORE`;
  map rows back into `SearchResult`/`IndexedDocument`. ✍️ CHIDUBEM (with coaching)

Concepts to explain first: what an embedding is, normalized vectors, cosine
similarity vs distance, why `1 - distance`, the pgvector `<=>` / `<->` operators.

### 2. Indexing pipeline — `ingestion/index.py` + `IndexingService`

Orchestrates existing pieces: connector.read_rows → verbalizer.verbalize →
embedder.embed → build `IndexedDocument` (deterministic `document_id`) →
vector_store.upsert. Batches embeds for speed.

- `IndexingService` orchestration + `document_id` construction. ✍️ CHIDUBEM
  (this is the heart of the pipeline; instructive)
- CLI entrypoint `python -m semantic_search_middleware.ingestion.index` and
  `make index` target. 🔧 CLAUDE

### 3. Config — `config/settings.py`

Add: `index_table = "support_tickets"`, `index_primary_key = "id"`,
`index_columns = ["subject","body","product","status","priority"]`. Matching
`.env.example` entries. 🔧 CLAUDE

### 4. Wire `/search` — `api/routes/search.py`

FastAPI dependency builds `SearchService(embedder, pgvector_store)` (embedder and
engine constructed once, cached). Replace the placeholder return with a real
call. 🔧 CLAUDE (DI wiring), with Chidubem reviewing the dependency lifecycle.

## Data flow

```
make index:  support_tickets rows → verbalize → embed(384) → documents (pgvector)
/search:     query → embed(384) → cosine search top_k → threshold → SearchResult + Citation
```

## Error handling

- Missing/empty source table → indexing exits with a clear message, non-zero code.
- Embedding dimension mismatch vs `EMBEDDING_DIMENSION` → fail fast at startup.
- `/search` with no indexed documents → returns empty `results` (not an error).
- DB unavailable → `/search` returns HTTP 503 with a clear message.

## Testing

- **Unit** (no DB): distance→score conversion and threshold filtering logic
  (pure function extracted so it's testable without Postgres). ✍️ CHIDUBEM writes
  the function; test written together.
- **Integration** (`tests/integration/`): `/search` end-to-end against a seeded
  DB, marked to skip when no `DATABASE_URL` reachable so CI stays green. 🔧 CLAUDE

## Verification

1. `docker compose up -d db`, then `make index` → prints count of indexed docs.
2. `uvicorn ...`, `POST /api/v1/search {"query":"can't log in after password reset"}`
   → returns relevant tickets, descending score, each with a citation.
3. Re-run `make index` → same document count (idempotent upsert), no duplicates.
4. `pytest` green with and without a database present.

## Open decisions (resolved)

- Source/index DB separation: **separate `source_data` DB** (matches settings).
- Indexing entrypoint: **CLI `make index`** (batch job), not an HTTP endpoint.
- `document_id`: **deterministic** `"<table>:<pk_value>"` (enables upsert + sync).
