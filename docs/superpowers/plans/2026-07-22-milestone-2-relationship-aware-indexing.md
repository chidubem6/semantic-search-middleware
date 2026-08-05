# Milestone 2 — Relationship-Aware Indexing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **⚠️ Working-model override (project CLAUDE.md):** This is a teaching repo. Tasks marked **✍️ CHIDUBEM** are hand-written by Chidubem with **hints only** — the plan deliberately gives the failing test and/or the interface contract but **NOT the solution code**. That omission is intentional and is *not* a plan defect. **Do NOT dispatch ✍️ tasks to subagents** and do NOT paste their implementations. Tasks marked **🔧 CLAUDE** are plumbing Claude writes and walks through; those carry full code.

**Goal:** Normalise the seed into related tables, add config-driven foreign-key-aware ("joined") verbalisation alongside the existing isolated strategy, and measure which retrieves better with recall@5.

**Architecture:** Config declares which foreign keys to follow and which descriptive columns to pull. The indexer batch-resolves those relations and hands them to a pure verbaliser; a comparison harness re-indexes the same rows under each strategy and reports recall@5 against a strategy-neutral, SQL-derived ground truth.

**Tech Stack:** Python 3.12, SQLAlchemy 2, Pydantic, PostgreSQL + pgvector, sentence-transformers, pytest.

## Global Constraints

- Verbaliser stays a **pure text function** — no DB access inside it; deterministic for fixed input.
- Relationships come from **config**, never from DB introspection of FK constraints.
- Descriptive columns (`customers.plan`, `customers.region`, `products.team`) live **only** in referenced tables, never as `support_tickets` columns.
- No unit test may require a live database or embedding model (use fakes / fixed inputs). The harness (a script) is the only DB-touching piece and is not a unit test.
- Commits: small, single-purpose, **no `Co-Authored-By` trailer, no "Generated with Claude Code" footer**.
- Checks must pass before commit: `ruff check .`, `ruff format --check .`, `mypy src`, `pytest`.

## File map

- `scripts/seed_source.sql` — **modify**: add `customers`, `products`, FK columns on `support_tickets`. 🔧
- `src/semantic_search_middleware/connectors/postgres.py` — **modify**: add `read_referenced_rows`. 🔧
- `src/semantic_search_middleware/domain/ports.py` — **modify**: extend `RelationalConnector` protocol. 🔧
- `src/semantic_search_middleware/config/settings.py` — **modify**: add `Relationship` model + `index_relationships`. ✍️
- `src/semantic_search_middleware/ingestion/verbaliser.py` — **modify**: add joined path. ✍️
- `src/semantic_search_middleware/ingestion/indexer.py` — **modify**: resolve relations, strategy select. 🔧
- `src/semantic_search_middleware/evaluation/recall.py` — **create**: `recall_at_k`. ✍️
- `scripts/compare_verbalisation.py` — **create**: comparison harness. 🔧
- `scripts/eval_queries.py` (or `.json`) — **create**: relational query set + relevance rules. (together)
- `docs/ROADMAP.md` — **modify**: fan-out Stretch bullet. 🔧
- `docs/adr/0002-explicit-relationship-config.md` — **create**: ADR. (together)
- Tests under `tests/unit/`. ✍️/🔧 as noted per task.

## Agreed cross-task interface (verbaliser ⇄ indexer)

Both the ✍️ verbaliser (Task 4) and the 🔧 indexer (Task 5) depend on one shared shape. **This is the contract:**

- `RowVerbaliser.verbalise(table: str, row: Mapping[str, Any], columns: Sequence[str], relations: Sequence[tuple[str, Mapping[str, Any]]] = ()) -> str`
- `relations` is a sequence of `(label, fields)` pairs already resolved for *this* row, where `fields` is `{descriptive_column: value}`. Empty `relations` ⇒ isolated output (byte-for-byte identical to today, so existing tests still pass).
- Chidubem owns how joined text is *formatted*; if he prefers a different `relations` shape, we change it here and in Task 5 together before Task 5 starts.

---

### Task 1: Normalise the seed into related tables 🔧 CLAUDE

**Files:**
- Modify: `scripts/seed_source.sql`

**Interfaces:**
- Produces: `customers(id, name, plan, region)`, `products(id, name, team)`, and `support_tickets` with `customer_id`/`product_id` FK columns. Later tasks and the harness rely on these names.

- [ ] **Step 1: Rewrite the seed** — add the two parent tables, seed them from the existing name/product arrays with deterministic descriptive attributes, and give `support_tickets` real FK columns.

```sql
\connect source_data

CREATE TABLE IF NOT EXISTS customers (
    id     SERIAL PRIMARY KEY,
    name   TEXT NOT NULL,
    plan   TEXT NOT NULL,   -- free | pro | enterprise  (joinable meaning; NOT on tickets)
    region TEXT NOT NULL    -- e.g. NA | EU | APAC
);

CREATE TABLE IF NOT EXISTS products (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    team TEXT NOT NULL       -- owning team (joinable meaning; NOT on tickets)
);

INSERT INTO customers (name, plan, region)
SELECT c.name,
       (ARRAY['free','pro','enterprise'])[1 + ((c.ord - 1) % 3)],
       (ARRAY['NA','EU','APAC'])[1 + ((c.ord - 1) % 3)]
FROM unnest(ARRAY['Ada','Blake','Chen','Diego','Emeka','Farah','Grace','Hiro','Ivy','Jonas'])
     WITH ORDINALITY AS c(name, ord);

INSERT INTO products (name, team)
SELECT p.name,
       (ARRAY['Identity','Payments','Core Platform','Billing','Desktop'])[p.ord]
FROM unnest(ARRAY['Web App','Mobile App','Public API','Billing Portal','Desktop Client'])
     WITH ORDINALITY AS p(name, ord);

CREATE TABLE IF NOT EXISTS support_tickets (
    id          SERIAL PRIMARY KEY,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    product     TEXT NOT NULL,
    status      TEXT NOT NULL,
    priority    TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL,
    customer_id INT NOT NULL REFERENCES customers(id),   -- declared FK: self-documenting + enforced
    product_id  INT NOT NULL REFERENCES products(id)
);
```

Then, in the existing `INSERT INTO support_tickets ... SELECT ... FROM generate_series(1,400) g, params p`, keep every current column and append two more using the **same** `g` arithmetic that already picks the customer name and product, so the FK matches the text:

```sql
    -- customer_id: same rotation the body already uses (g % 10) → customers.id
    1 + (g % array_length(p.customers, 1)),
    -- product_id: same rotation the product column already uses (g % 5) → products.id
    1 + (g % array_length(p.products, 1)),
```

(Add the two `INSERT` target columns `customer_id, product_id` and these two `SELECT` expressions. Because `customers`/`products` are seeded in array order, `customers.id = ord` and `products.id = ord`, so the arithmetic lines up.)

- [ ] **Step 2: Re-seed and verify integrity**

Run (from the DB container / psql):
```bash
# re-run the init + seed against a fresh source_data (however the project bootstraps it)
psql "$SOURCE_DATABASE_URL" -c "SELECT count(*) FROM support_tickets;"        # expect 400
psql "$SOURCE_DATABASE_URL" -c "SELECT count(*) FROM customers;"              # expect 10
psql "$SOURCE_DATABASE_URL" -c "SELECT count(*) FROM products;"               # expect 5
psql "$SOURCE_DATABASE_URL" -c "SELECT count(*) FROM support_tickets t JOIN customers c ON t.customer_id=c.id;"  # expect 400 (no orphans)
```
Expected: counts as annotated; a deliberately bad insert (`customer_id=99999`) is rejected by the constraint.

- [ ] **Step 3: Commit**
```bash
git add scripts/seed_source.sql
git commit -m "feat(milestone-2): normalise seed into customers and products"
```

---

### Task 2: Batch referenced-row lookup on the connector 🔧 CLAUDE

**Files:**
- Modify: `src/semantic_search_middleware/domain/ports.py`
- Modify: `src/semantic_search_middleware/connectors/postgres.py`
- Test: `tests/unit/test_postgres_connector.py` (create; pure-Python test of the mapping logic via a thin seam — see step 1)

**Interfaces:**
- Produces: `read_referenced_rows(table: str, key: str, key_values: Iterable[Any], columns: Sequence[str]) -> dict[Any, dict[str, Any]]` — a `{key_value: {column: value}}` lookup. One `WHERE key IN (...)` query, not per-row. Task 5 consumes this.

- [ ] **Step 1: Write the failing test** — assert the row list → keyed-map shaping (the part worth testing without a DB). Extract the shaping into a module-level pure helper so it is unit-testable:

```python
# tests/unit/test_postgres_connector.py
from semantic_search_middleware.connectors.postgres import index_rows_by_key


def test_index_rows_by_key_builds_lookup_keyed_on_the_key_column():
    rows = [
        {"id": 1, "name": "Ada", "plan": "enterprise"},
        {"id": 2, "name": "Blake", "plan": "free"},
    ]
    lookup = index_rows_by_key(rows, "id")
    assert lookup == {
        1: {"id": 1, "name": "Ada", "plan": "enterprise"},
        2: {"id": 2, "name": "Blake", "plan": "free"},
    }


def test_index_rows_by_key_handles_no_rows():
    assert index_rows_by_key([], "id") == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_postgres_connector.py -v`
Expected: FAIL with `ImportError: cannot import name 'index_rows_by_key'`.

- [ ] **Step 3: Implement** the helper and the connector method.

```python
# connectors/postgres.py  (add imports: Mapping already covered by Any; add Iterable if missing)
def index_rows_by_key(rows: Iterable[dict[str, Any]], key: str) -> dict[Any, dict[str, Any]]:
    return {row[key]: dict(row) for row in rows}


# inside PostgresConnector:
    def read_referenced_rows(
        self,
        table: str,
        key: str,
        key_values: Iterable[Any],
        columns: Sequence[str],
    ) -> dict[Any, dict[str, Any]]:
        wanted = list(dict.fromkeys(key_values))  # de-dup, preserve order
        if not wanted:
            return {}
        reflected = Table(table, self._metadata, autoload_with=self._engine)
        selected = [reflected.c[key], *[reflected.c[c] for c in columns]]
        stmt = select(*selected).where(reflected.c[key].in_(wanted))
        with self._engine.connect() as connection:
            rows = [dict(r) for r in connection.execute(stmt).mappings()]
        return index_rows_by_key(rows, key)
```

Add to the protocol:
```python
# domain/ports.py, inside RelationalConnector
    def read_referenced_rows(
        self, table: str, key: str, key_values: Iterable[Any], columns: Sequence[str]
    ) -> dict[Any, dict[str, Any]]: ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_postgres_connector.py -v` → PASS. Then `mypy src` → clean.

- [ ] **Step 5: Commit**
```bash
git add src/semantic_search_middleware/connectors/postgres.py src/semantic_search_middleware/domain/ports.py tests/unit/test_postgres_connector.py
git commit -m "feat(milestone-2): batch-load referenced rows by key"
```

---

### Task 3: Relationship config spec ✍️ CHIDUBEM

**Files:**
- Modify: `src/semantic_search_middleware/config/settings.py`
- Test: `tests/unit/test_settings_relationships.py` (you write this)

**Interfaces:**
- Produces: a `Relationship` Pydantic model with fields `local_column`, `referenced_table`, `referenced_key`, `columns: list[str]`, `label` — and `Settings.index_relationships: list[Relationship]` defaulting to the two entries below. Task 5 reads these fields by exactly these names.

**Your task (hints, not code):**
- Model the relationship as a small `pydantic.BaseModel`, mirroring how `Settings` already declares typed fields with defaults (look at `index_columns`).
- The default value should describe the two real relationships:
  - `customer_id → customers(id)`, pull `["name", "plan", "region"]`, label `"customer"`.
  - `product_id → products(id)`, pull `["name", "team"]`, label `"product"`.
- **Hint on the one gotcha:** a mutable default (a list of models) on a Pydantic settings field needs the same treatment `index_columns` gets — look at how that field avoids the shared-mutable-default trap, and do the same.
- **The test is yours to write** (this is your named growth area). A good shape: load settings, assert there are two relationships, and assert the `customer` one pulls `plan` and `region` but that neither `plan` nor `region` appears in `index_columns` (that assertion *encodes the whole experiment's validity* — the descriptive fields must be reachable only via join). Escalating hints available if you get stuck — ask and I'll give one level at a time.

- [ ] **Step 1:** Write your failing test in `tests/unit/test_settings_relationships.py`.
- [ ] **Step 2:** Run it, watch it fail for the right reason (`AttributeError`/`ImportError`).
- [ ] **Step 3:** Write the `Relationship` model and `index_relationships` default.
- [ ] **Step 4:** `pytest tests/unit/test_settings_relationships.py -v` → PASS; `mypy src` → clean.
- [ ] **Step 5:** Commit — `feat(milestone-2): declare foreign-key relationships in config`.

---

### Task 4: Joined verbalisation ✍️ CHIDUBEM (core)

**Files:**
- Modify: `src/semantic_search_middleware/ingestion/verbaliser.py`
- Test: `tests/unit/test_verbaliser.py` (you write this)

**Interfaces:**
- Consumes: the `relations` contract from the "Agreed cross-task interface" section above.
- Produces: `verbalise(..., relations=())` extended so that non-empty `relations` appends labelled related fields to the existing isolated text; empty `relations` is unchanged.

**Your task (hints, not code):**
- Keep today's isolated line exactly as-is when `relations` is empty (so existing behaviour and the indexer's isolated path don't move).
- When relations are present, append them in a **deterministic** order (the order given), each as `label: field/value` text you choose — the goal is that a query mentioning `enterprise` or a product `team` can now match.
- Decide how to render one relation's `fields` dict into text (e.g. `customer: Ada (enterprise, EU)` vs `customer: name=Ada; plan=enterprise`). Justify your choice — an interviewer will ask why. Determinism matters: dict iteration order follows the configured `columns`, so don't sort or reorder.
- **The test is yours.** Cover: (a) empty relations ⇒ identical to the isolated string; (b) with two relations ⇒ both labels and the pulled values appear, and *only* the configured columns appear (no leaked id/timestamp). Ask for graded hints if stuck.

- [ ] **Step 1:** Write your failing tests.
- [ ] **Step 2:** Run → fail for the right reason.
- [ ] **Step 3:** Implement the joined path.
- [ ] **Step 4:** `pytest tests/unit/test_verbaliser.py -v` → PASS; full `pytest` still green (isolated unchanged).
- [ ] **Step 5:** Commit — `feat(milestone-2): fold related fields into verbalised text`.

---

### Task 5: Indexer resolves relations + strategy select 🔧 CLAUDE (walked through)

**Files:**
- Modify: `src/semantic_search_middleware/ingestion/indexer.py`
- Test: `tests/unit/test_indexer_joined.py` (create)

**Interfaces:**
- Consumes: `Relationship` (Task 3), `read_referenced_rows` (Task 2), `verbalise(..., relations=...)` (Task 4).
- Produces: `index_table(..., relationships: Sequence[Relationship] = (), strategy: str = "isolated")`. `"isolated"` ignores relationships (today's behaviour). `"joined"` batch-resolves each relationship and passes per-row `relations` to the verbaliser.

- [ ] **Step 1: Write the failing test** using fakes (no DB, no embedder):

```python
# tests/unit/test_indexer_joined.py
from semantic_search_middleware.config.settings import Relationship
from semantic_search_middleware.ingestion.indexer import IndexingService
from semantic_search_middleware.ingestion.verbaliser import RowVerbaliser


class FakeConnector:
    def read_rows(self, table, columns):
        return [{"id": 1, "subject": "login broken", "customer_id": 7}]

    def read_referenced_rows(self, table, key, key_values, columns):
        assert list(key_values) == [7]           # batch-resolved from the base rows
        return {7: {"name": "Ada", "plan": "enterprise", "region": "EU"}}


class CapturingEmbedder:
    def __init__(self):
        self.texts = None

    def embed(self, texts):
        self.texts = list(texts)
        return [[0.0] for _ in texts]


class NullStore:
    def upsert(self, documents, vectors):
        pass


def test_joined_strategy_embeds_text_containing_related_fields():
    embedder = CapturingEmbedder()
    service = IndexingService(FakeConnector(), RowVerbaliser(), embedder, NullStore())
    rel = Relationship(
        local_column="customer_id", referenced_table="customers",
        referenced_key="id", columns=["name", "plan", "region"], label="customer",
    )

    service.index_table("support_tickets", "id", ["subject"], relationships=[rel], strategy="joined")

    assert "enterprise" in embedder.texts[0]     # only reachable via the join
    assert "Ada" in embedder.texts[0]
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/unit/test_indexer_joined.py -v`
Expected: FAIL — `index_table()` got an unexpected keyword `relationships`.

- [ ] **Step 3: Implement** — extend `index_table`:

```python
def index_table(
    self,
    table: str,
    primary_key: str,
    content_columns: Sequence[str],
    relationships: Sequence["Relationship"] = (),
    strategy: str = "isolated",
) -> int:
    rows = list(self._connector.read_rows(table, [*content_columns, primary_key]))

    resolved: dict[str, dict[Any, dict[str, Any]]] = {}
    if strategy == "joined":
        for rel in relationships:
            key_values = [r[rel.local_column] for r in rows]
            resolved[rel.local_column] = self._connector.read_referenced_rows(
                rel.referenced_table, rel.referenced_key, key_values, rel.columns
            )

    documents, texts = [], []
    for row in rows:
        relations: list[tuple[str, dict[str, Any]]] = []
        if strategy == "joined":
            for rel in relationships:
                ref = resolved[rel.local_column].get(row[rel.local_column])
                if ref is not None:
                    relations.append((rel.label, ref))

        text = self._verbaliser.verbalise(table, row, content_columns, relations)
        pk_value = str(row[primary_key])
        texts.append(text)
        documents.append(
            IndexedDocument(
                document_id=f"{table}:{pk_value}",
                text=text,
                source=SourceReference(
                    table=table, primary_key=primary_key, primary_key_value=pk_value
                ),
            )
        )

    if not documents:
        return 0
    vectors = self._embedder.embed(texts)
    self._vector_store.upsert(documents, vectors)
    return len(documents)
```

Add `from semantic_search_middleware.config.settings import Relationship` and `from typing import Any` at the top. Note `read_rows` is now materialised once (we iterate it twice: for keys and for documents).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_indexer_joined.py -v` → PASS. Full `pytest` green (isolated default unchanged). `mypy src` clean.

- [ ] **Step 5: Commit**
```bash
git add src/semantic_search_middleware/ingestion/indexer.py tests/unit/test_indexer_joined.py
git commit -m "feat(milestone-2): resolve relations and select verbalisation strategy"
```

---

### Task 6: recall@5 metric ✍️ CHIDUBEM (core)

**Files:**
- Create: `src/semantic_search_middleware/evaluation/__init__.py` (empty) 🔧
- Create: `src/semantic_search_middleware/evaluation/recall.py` ✍️
- Test: `tests/unit/test_recall.py` — **provided below** as your executable spec.

**Interfaces:**
- Produces: `recall_at_k(retrieved: Sequence[str], relevant: Set[str], k: int) -> float`. `retrieved` is the ranked list of source-row ids from a search (best first); `relevant` is the ground-truth id set for that query; return the fraction of `relevant` found within the top `k`. Task 7 consumes it.

The test is given (so your energy goes to the scoring math, not the harness). **You write `recall.py` to make it pass — hints, not code, if you're stuck.**

- [ ] **Step 1: Add the provided failing test**

```python
# tests/unit/test_recall.py
import pytest

from semantic_search_middleware.evaluation.recall import recall_at_k


def test_all_relevant_in_top_k():
    assert recall_at_k(["3", "1", "2", "9"], {"1", "2", "3"}, k=5) == 1.0


def test_partial_recall_counts_only_relevant_within_k():
    # relevant = {1,2,3}; top-3 window = [1,4,2] → found 2 of 3
    assert recall_at_k(["1", "4", "2", "3"], {"1", "2", "3"}, k=3) == pytest.approx(2 / 3)


def test_k_larger_than_results_is_fine():
    assert recall_at_k(["1"], {"1", "2"}, k=5) == pytest.approx(0.5)


def test_no_relevant_rows_defined_returns_zero_not_crash():
    assert recall_at_k(["1", "2"], set(), k=5) == 0.0
```

- [ ] **Step 2:** Run → fail (`ImportError`).
- [ ] **Step 3:** Write `recall_at_k`. **Hints:** take the first `k` of `retrieved`; intersect with `relevant`; divide by `len(relevant)`; guard the empty-`relevant` case (that last test tells you the required behaviour — don't divide by zero). No numpy needed.
- [ ] **Step 4:** `pytest tests/unit/test_recall.py -v` → PASS.
- [ ] **Step 5:** Commit — `feat(milestone-2): add recall@k retrieval metric`.

---

### Task 7: Comparison harness + query labels (🔧 CLAUDE scaffold · together for labels)

**Files:**
- Create: `scripts/eval_queries.py` — query set + ground-truth SQL (together)
- Create: `scripts/compare_verbalisation.py` — the harness 🔧

**Interfaces:**
- Consumes: `IndexingService.index_table(..., strategy=...)`, `Settings.index_relationships`, `recall_at_k`, `PgVectorStore.search`, `SentenceTransformerEmbedder.embed`.

**Ground truth is strategy-neutral (avoids the circularity we discussed):** each query's relevant ids come from a **SQL rule over the source DB**, not from either strategy's text. Example entry:

```python
# scripts/eval_queries.py
QUERIES = [
    {
        "query": "enterprise customers who cannot log in after a password reset",
        # relevant = login/reset theme AND customer on the enterprise plan
        "relevant_sql": """
            SELECT t.id FROM support_tickets t
            JOIN customers c ON t.customer_id = c.id
            WHERE t.subject = 'Cannot log in after password reset'
              AND c.plan = 'enterprise'
        """,
    },
    # ~8–12 total, mixing customer-attribute and product-team relational queries.
]
```
We author the full list together after Task 1 fixes the seed, so the SQL matches real data.

- [ ] **Step 1: Write `scripts/eval_queries.py`** with the `QUERIES` list (built together).

- [ ] **Step 2: Write the harness** 🔧:

```python
# scripts/compare_verbalisation.py
from sqlalchemy import create_engine, text

from scripts.eval_queries import QUERIES
from semantic_search_middleware.config import get_settings
from semantic_search_middleware.connectors.postgres import PostgresConnector
from semantic_search_middleware.embeddings.sentence_transformer import SentenceTransformerEmbedder
from semantic_search_middleware.evaluation.recall import recall_at_k
from semantic_search_middleware.ingestion.indexer import IndexingService
from semantic_search_middleware.ingestion.verbaliser import RowVerbaliser
from semantic_search_middleware.vectorstores.pgvector_store import PgVectorStore

K = 5


def ground_truth(engine, sql):
    with engine.connect() as conn:
        return {str(r[0]) for r in conn.execute(text(sql))}


def run_strategy(strategy, settings, embedder, store):
    IndexingService(
        PostgresConnector(settings.source_database_url), RowVerbaliser(), embedder, store
    ).index_table(
        settings.index_table, settings.index_primary_key, settings.index_columns,
        relationships=settings.index_relationships, strategy=strategy,
    )
    source_engine = create_engine(settings.source_database_url)
    scores = []
    for q in QUERIES:
        relevant = ground_truth(source_engine, q["relevant_sql"])
        vector = embedder.embed([q["query"]])[0]
        hits = store.search(vector, top_k=K)
        retrieved = [h.document.source.primary_key_value for h in hits]
        scores.append(recall_at_k(retrieved, relevant, K))
    return sum(scores) / len(scores)


def main():
    settings = get_settings()
    embedder = SentenceTransformerEmbedder(settings.embedding_model)
    store = PgVectorStore(settings.database_url, settings.embedding_dimension)
    # Sequential re-index: deterministic document_ids overwrite, so both strategies
    # reuse the one `documents` table — no second namespace needed.
    for strategy in ("isolated", "joined"):
        mean_recall = run_strategy(strategy, settings, embedder, store)
        print(f"{strategy:>8}  mean recall@{K} = {mean_recall:.3f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run it** (DB up, Ollama not needed):

Run: `python -m scripts.compare_verbalisation`
Expected: two lines, `isolated` and `joined`, each with a mean recall@5. Record the numbers.

- [ ] **Step 4: Commit**
```bash
git add scripts/eval_queries.py scripts/compare_verbalisation.py
git commit -m "feat(milestone-2): compare isolated vs joined recall@5"
```

---

### Task 8: Docs & ADR (🔧 CLAUDE scaffold · ADR reasoning together)

**Files:**
- Modify: `docs/ROADMAP.md` — add under **Stretch**: a one-to-many fan-out bullet (following a ticket's many comments; needs a summarise/truncate rule; deferred here).
- Create: `docs/adr/0002-explicit-relationship-config.md` — mirror the `0001` structure (Status / Context / Decision / Consequences). Decision: relationships come from explicit config, not DB introspection. Context/Consequences: the read-only-middleware reasoning (can't assume FK constraints exist; must control which columns to embed to limit dilution). **Chidubem drafts the reasoning** (it's his interview artifact); Claude formats.
- Modify: `docs/superpowers/specs/2026-07-22-...-design.md` — if the recorded strategy result is decisive, add a one-line "Result:" note with the recall@5 numbers.

- [ ] **Step 1:** Update `ROADMAP.md`.
- [ ] **Step 2:** Write the ADR (reasoning from Chidubem).
- [ ] **Step 3:** Record the recall@5 result.
- [ ] **Step 4:** Commit — `docs: record relationship-aware indexing decisions and results`.

---

## Self-Review

**Spec coverage:**
- Normalise seed + FKs → Task 1 ✅
- Config-driven relationship spec → Task 3 ✅
- Two verbalisation strategies (isolated/joined) → Task 4 (verbaliser) + Task 5 (indexer strategy) ✅
- Measure both / recall@5 → Task 6 (metric) + Task 7 (harness) ✅
- Strategy-neutral relevance definition → Task 7 (`relevant_sql` over source DB) ✅
- Deferred fan-out recorded → Task 8 (ROADMAP Stretch) + spec Deferred section ✅
- ADR: explicit config over introspection → Task 8 ✅
- Chidubem writes ≥1 test himself → Tasks 3 and 4 (his tests) ✅
- Pure verbaliser / indexer resolves joins → cross-task interface + Task 5 ✅

**Placeholder scan:** No `TBD`/`TODO`. ✍️ tasks intentionally omit solution code per the working-model override (documented at top) — not placeholders.

**Type consistency:** `Relationship` fields (`local_column`, `referenced_table`, `referenced_key`, `columns`, `label`) are used identically in Tasks 3, 5, 7. `read_referenced_rows` signature matches between Task 2 (impl) and Task 5 (consumer). `verbalise(..., relations=())` contract matches between Tasks 4 and 5. `recall_at_k(retrieved, relevant, k)` matches between Tasks 6 and 7.

**Note on spec deviation:** spec said "two namespaces"; plan simplified to sequential re-index (deterministic ids overwrite) — no vector-store change. Recorded in Task 7 comment and here.
