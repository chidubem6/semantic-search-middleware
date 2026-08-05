# Milestone 1 — Grounded Chat Design

**Date:** 2026-07-20
**Status:** Approved (design), pending spec review

## Context

Milestone 0 proved the vertical slice: `POST /api/v1/search` embeds a query, runs
a cosine search against pgvector, filters by `MIN_SIMILARITY_SCORE`, and returns
ranked `SearchResult`s with citations.

Milestone 1 turns retrieval into **grounded generation**. `POST /api/v1/chat`
currently returns a hard-coded placeholder. This chunk makes it real: retrieve
context, assemble a grounded prompt, call a local LLM via Ollama, and return an
answer with citations — or abstain when retrieval finds nothing.

Per the agreed working model, **Chidubem writes the instructive core logic**
(✍️ CHIDUBEM) and **Claude scaffolds the plumbing** (🔧 CLAUDE). Every concept is
explained before the code.

Already in place and unused: `GROUNDED_SYSTEM_PROMPT` in `rag/prompts.py`, the
`ChatRequest`/`ChatResponse` schemas (including `supported: bool`), and the
`LLM_PROVIDER` / `LLM_MODEL` / `OLLAMA_BASE_URL` entries in `.env.example`.

## Goals

- `POST /api/v1/chat` returns an LLM answer grounded in retrieved database rows.
- Abstain (`supported: false`, empty `citations`, **no LLM call**) when retrieval
  returns nothing above the similarity threshold.
- Every response cites the source rows the answer was based on.
- Tests run with no Ollama and no database.

## Non-goals (later milestones)

- Post-generation faithfulness / citation validation — deferred until Milestone 5
  gives us an eval set to measure it against.
- Conversation history. `conversation_id` is echoed back, not used to build
  multi-turn context. Each request is answered from retrieval alone.
- Streaming responses, tool calling, hosted-LLM adapters.
- Foreign-key-aware context (Milestone 2), hybrid retrieval (Milestone 3).

## Design decisions

**Abstention = retrieval gate only.** If retrieval returns zero results, we
refuse to answer without calling the LLM. This is deterministic, costs nothing,
and is testable without a model. `PgVectorStore` already drops results below
`MIN_SIMILARITY_SCORE`, so weak retrieval arrives at `ChatService` as an empty
list — abstention falls out of a guarantee Milestone 0 already established.

Rejected: asking the LLM to self-report insufficiency (trusting the model to
grade itself is the failure mode RAG exists to avoid) and citation-marker
validation (needs prompt-format machinery that belongs with the eval work).

**Citations = every retrieved context row**, in score order. Honest — "these are
the records the answer was based on" — and requires no parsing of model output.
Accepted cost: a cited row may not have influenced the answer, so citation
precision is loose. Tightening it is the deferred citation-validation work.

**`ChatService` composes `SearchService`** rather than taking `Embedder` and
`VectorStore` directly, so retrieval logic exists in exactly one place. When
hybrid retrieval lands in Milestone 3, only `SearchService` changes.

## Components

### 1. `LlmClient` port — `domain/ports.py` 🔧 CLAUDE

```python
class LlmClient(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str: ...
```

Two strings in, one string out. Same role `VectorStore` plays for pgvector:
`ChatService` must not know that HTTP, Ollama, or llama3.2 exist.

### 2. `OllamaClient` — `llm/ollama.py` (new package) 🔧 CLAUDE

`POST {OLLAMA_BASE_URL}/api/chat` with `stream: false` and a two-message payload
(system + user); returns `message.content`. Owns its timeout and raises a
domain-level error on transport failure or non-200.

### 3. Context builder — `rag/prompts.py` ✍️ CHIDUBEM

`build_context_prompt(question, results) -> str`. Formats `list[SearchResult]`
into a context block where each row is labelled with its source table and primary
key, followed by the user's question. The RAG counterpart to the verbaliser, and
a near-certain interview question ("how did you format retrieved context?").
Must be deterministic for a fixed input.

### 4. `ChatService` — `services/chat_service.py` ✍️ CHIDUBEM

```
results = search_service.search(message, top_k)
if not results:
    -> answer = refusal text, citations = [], supported = False   # no LLM call
prompt = build_context_prompt(message, results)
answer = llm.complete(GROUNDED_SYSTEM_PROMPT, prompt)
-> answer, citations = [Citation from r.document.source for r in results], supported = True
```

Returns a domain result; the route maps it to `ChatResponse` and fills
`conversation_id` (echoed, or a fresh `uuid4`).

### 5. Config + wiring 🔧 CLAUDE

- `config/settings.py`: `llm_provider`, `llm_model`, `ollama_base_url`,
  `llm_timeout_seconds`. `.env.example` already carries the first three.
- `api/dependencies.py`: `get_chat_service()`, `@lru_cache`, reusing the cached
  `get_search_service()`.
- `api/routes/chat.py`: `Depends(get_chat_service)`, placeholder removed.

## Data flow

```
/chat: message → SearchService.search → top_k SearchResults
       ├─ empty  → abstain (supported=false, no citations, no LLM call)
       └─ hits   → build_context_prompt → OllamaClient.complete
                   → answer + one Citation per retrieved row (supported=true)
```

## Error handling

- Ollama unreachable / times out / non-200 → HTTP 503 with a clear message. We do
  **not** silently degrade to an ungrounded or empty answer.
- Empty retrieval → HTTP 200 with `supported: false`. Not an error; it is the
  system working correctly.
- Database unavailable → HTTP 503, matching `/search`.

## Testing

No test touches Ollama or Postgres.

- **Unit — `ChatService`** with a fake `SearchService` and a recording fake
  `LlmClient`:
  - empty retrieval → `supported is False`, `citations == []`, **and the fake
    records zero LLM calls** (this assertion is the point of the test);
  - hits → answer comes from the LLM, one citation per result, `supported is True`.
- **Unit — context builder**: deterministic output for a fixed result list;
  contains each row's table and primary-key value.
- **Integration — `/api/v1/chat`** via FastAPI dependency overrides, following
  the existing `tests/integration/test_search.py` pattern.

## Verification

1. `pytest`, `ruff check .`, `ruff format --check .`, `mypy src` all green.
2. With Ollama running and the index populated:
   `POST /api/v1/chat {"message": "how do I fix a failed password reset?"}`
   → a grounded answer, `supported: true`, citations pointing at real ticket IDs.
3. `POST /api/v1/chat {"message": "what is the capital of France?"}`
   → `supported: false`, no citations, and no request reaches Ollama.
4. Stop Ollama, repeat step 2 → HTTP 503, not a fabricated answer.
