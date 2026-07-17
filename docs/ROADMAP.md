# MVP roadmap

## Milestone 0 — Prove the vertical slice

- Pick one source table with 100–1,000 rows.
- Configure indexed columns and primary key.
- Verbalise rows.
- Generate local embeddings.
- Store them in pgvector.
- Return top-5 matches from `/search` with source citations.

**Do not build the chatbot before this works.** Retrieval quality is the foundation.

## Milestone 1 — Grounded chat

- Build prompt assembly from retrieved rows.
- Add an Ollama or hosted LLM adapter.
- Return abstention when retrieval is weak.
- Return citations for each answer.

## Milestone 2 — Relationship-aware indexing

- Follow configured foreign keys.
- Compare isolated-row and joined-context verbalisation.
- Record retrieval metrics for both strategies.

## Milestone 3 — Hybrid retrieval

- Add PostgreSQL full-text search.
- Fuse lexical and semantic rankings.
- Test exact names, identifiers, and paraphrases.

## Milestone 4 — Synchronisation

- Add a deterministic document ID and source-row checksum.
- Upsert changed rows and delete removed rows.
- Start with a scheduled sync; CDC is optional.

## Milestone 5 — Evaluation

- Create 30–50 questions with expected rows and expected answers.
- Measure recall@5, answer correctness, faithfulness, abstention rate, and latency.
- Compare against an ungrounded LLM baseline.

## Stretch — Query routing

Route aggregate and numeric questions to a guarded text-to-SQL path. Vector search cannot reliably count, total, or aggregate records.
