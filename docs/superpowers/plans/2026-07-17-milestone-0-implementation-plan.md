# Milestone 0 — Implementation Plan (learning-loop build order)

Derived from `docs/superpowers/specs/2026-07-17-milestone-0-vertical-slice-design.md`.
Each chunk lists the concept to teach first, who writes it (✍️ Chidubem /
🔧 Claude), and how to verify. Run each as a learning loop:
**teach → he writes → he explains back → verify → next.**

## Chunk 1 — Stand up the two databases + sample data 🔧 CLAUDE
- **Teach first:** what pgvector is; why a separate `source_data` DB; what SQL DDL/seed is.
- Update `docker-compose.yml` + `scripts/init.sql` to create `source_data` and
  `semantic_search`; add `scripts/seed_source.sql` (~400 synthetic support tickets).
- **Verify:** `docker compose up -d db`; connect and `SELECT count(*) FROM support_tickets;` → ~400.

## Chunk 2 — Config for the indexed table 🔧 CLAUDE (Chidubem reviews)
- **Teach first:** how settings map to `.env`; lists in settings.
- Add `index_table`, `index_primary_key`, `index_columns` to `settings.py` + `.env.example`.
- **Verify:** `python -c "from ...config import get_settings; print(get_settings().index_columns)"`.

## Chunk 3 — The pgvector `documents` table + `upsert` 🔧 CLAUDE (Chidubem reviews)
- **Teach first:** what a `vector(384)` column is; the `documents` schema; what `upsert` does.
- Define the SQLAlchemy table + `PgVectorStore.__init__` + `upsert` (INSERT ... ON CONFLICT).
- **Verify:** a quick script inserts one fake document and reads it back.

## Chunk 4 — The similarity `search()` ✍️ CHIDUBEM (the core learning piece)
- **Teach first (the big one):** embeddings, vector space, cosine similarity vs
  distance, the pgvector `<=>` operator, why `score = 1 - distance`, the threshold.
- Chidubem writes `PgVectorStore.search()`: embed-free (takes a query vector),
  order by `<=>`, limit `top_k`, convert distance→score, drop below `MIN_SIMILARITY_SCORE`,
  map rows → `SearchResult`.
- **Extract** the distance→score+threshold logic as a small pure function for unit testing.
- **Verify:** unit test on the pure function; explain-back on cosine similarity.

## Chunk 5 — The indexing pipeline ✍️ CHIDUBEM
- **Teach first:** orchestration, deterministic `document_id`, batching embeds.
- Chidubem writes `IndexingService` wiring connector → verbaliser → embedder →
  `document_id` → `upsert`. Claude adds the `python -m ...ingestion.index` CLI + `make index`.
- **Verify:** `make index` prints indexed count; re-run → same count (idempotent).

## Chunk 6 — Wire `/search` 🔧 CLAUDE (Chidubem reviews the DI)
- **Teach first:** FastAPI dependency injection lifecycle.
- Add a dependency building `SearchService(embedder, PgVectorStore)`; replace the
  placeholder in `api/routes/search.py`.
- **Verify:** `POST /api/v1/search {"query":"can't log in after password reset"}`
  returns relevant tickets, descending score, with citations.

## Chunk 7 — Tests + polish 🔧/✍️ together
- Unit: distance→score/threshold (from Chunk 4). Integration: `/search` end-to-end,
  skipped when no DB so CI stays green. Update README with a "run the demo" section.
- **Verify:** `pytest` green with and without a database present.

## Definition of done
`make index` populates pgvector from `support_tickets`; `/search` returns ranked,
cited results; re-indexing is idempotent; tests pass; Chidubem can explain
embeddings, cosine search, and the architecture in his own words.
