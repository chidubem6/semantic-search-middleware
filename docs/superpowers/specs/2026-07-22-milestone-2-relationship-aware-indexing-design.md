# Milestone 2 — Relationship-Aware Indexing Design

**Date:** 2026-07-22
**Status:** Approved (design), pending spec review

## Context

Milestones 0 and 1 index a single flat table. `support_tickets` is denormalised:
the customer is baked into the `body` text as a string, `product` is a plain text
column, and there are **no foreign keys and no related tables**. So today's
`RowVerbaliser` verbalises each row from its own columns only — "isolated"
verbalisation.

Milestone 2 asks whether **following foreign keys into referenced tables** and
folding their descriptive fields into the verbalised text ("joined" verbalisation)
improves retrieval. Because the current seed has nothing to join to, the milestone
begins by **normalising the seed into related tables**, then builds both
strategies and **measures** which retrieves better. The point is not to assume
joins help — it is to prove it with a metric.

Per the agreed working model, **Chidubem writes the instructive core logic**
(✍️ CHIDUBEM) and **Claude scaffolds the plumbing** (🔧 CLAUDE). Every concept is
explained before the code.

## Goals

- Normalise the synthetic seed into `customers` and `products` tables with real,
  declared foreign-key constraints on `support_tickets`.
- Add a **config-driven relationship spec**: the operator declares which foreign
  keys to follow and which descriptive columns to pull — not DB introspection.
- Produce **two** verbalisation strategies from the same rows: isolated (own
  columns) and joined (own columns + resolved related fields).
- **Measure both**: a comparison harness runs a hand-labelled set of relational
  queries against each strategy and reports **recall@5** side by side.

## Non-goals (later milestones / deferred)

- **One-to-many fan-out** (e.g. a ticket with many `comments`). Deferred — needs a
  summarisation/truncation rule so many child rows don't explode and dilute the
  vector. Recorded as a Stretch item, not scheduled. See "Deferred" below.
- **DB introspection** of foreign-key constraints to auto-discover relationships.
  Rejected as the source of truth (see Design decisions); could later *suggest*
  config, but selection stays explicit.
- Full evaluation rigor — MRR, faithfulness, 30–50 questions, baseline comparison.
  Stays in Milestone 5. This milestone builds only enough measurement to choose a
  strategy; its query set becomes seed material for Milestone 5.
- Hybrid lexical/vector retrieval (Milestone 3).

## Design decisions

**Normalise so the experiment is valid.** `plan`, `region` (on `customers`) and
`team` (on `products`) live **only** in the referenced tables — they are *not*
columns on `support_tickets`. Isolated verbalisation is therefore structurally
blind to them, and only joined verbalisation can surface them. This deliberate
split is what creates a measurable gap between the strategies. The customer *name*
may remain in the ticket `body` (realistic — customers are named in ticket text);
the *joinable meaning* is the attributes that are not.

**Explicit relationship config over DB introspection.** A read-only middleware
over someone else's database cannot assume the source declared its FK constraints,
and even when it did, blindly embedding every linked column maximises dilution.
The operator declares which relationships and which descriptive columns carry
meaning — the same onboarding surface as the existing `index_table` /
`index_columns`. This keeps the verbaliser deterministic and gives explicit
control over dilution. Captured as an ADR.

**Declare FK constraints in the seed anyway.** They cost two words, guarantee
referential integrity, and make the schema self-documenting — but the verbaliser
follows the *config*, never the constraints, so the design still works against a
real DB that has no constraints declared.

**Joins resolved by the indexer, not the verbaliser.** The verbaliser stays a
**pure text function** (row + resolved relations → text, no DB access). The
indexer batch-loads referenced rows into a lookup keyed by the referenced key
(avoids N+1 queries) and passes the resolved fields in. This preserves
determinism and testability without a database.

## Components

### 1. Seed normalisation — `scripts/seed_source.sql` 🔧 CLAUDE

- New `customers` (`id` PK, `name`, `plan`, `region`) and `products` (`id` PK,
  `name`, `team`), seeded from the existing rotating arrays.
- `support_tickets` gains `customer_id INT REFERENCES customers(id)` and
  `product_id INT REFERENCES products(id)`, populated deterministically.
- Keep row counts stable so retrieval behaviour stays comparable to Milestone 0/1.

### 2. Relationship config — `config/settings.py` ✍️ CHIDUBEM

An `index_relationships` spec: a list where each entry names the `local_column`,
`referenced_table`, `referenced_key`, the descriptive `columns` to pull, and a
human `label`. Chidubem designs the exact shape (Pydantic model vs. typed dict)
and decides whether raw FK ids are excluded from isolated text. Instructive:
this *is* the integration contract for a pluggable source DB.

### 3. Referenced-row lookup — `connectors/postgres.py` 🔧 CLAUDE

A method to fetch referenced rows for a relationship: given a table, key column,
a set of key values, and the columns to pull, return a `{key_value: row}` lookup.
Batch (one `WHERE key IN (...)` query per relationship), not per-row.

### 4. Two verbalisation strategies — `ingestion/verbaliser.py` ✍️ CHIDUBEM

Keep the existing isolated `verbalise`. Add a **joined** path that accepts the
resolved related fields and folds them into the text under their labels, e.g.
`... customer: Acme Corp (enterprise, EU); product: Auth API (Identity team).`
Chidubem writes the joining logic; must stay deterministic for fixed input.

### 5. Indexer wiring — `ingestion/indexer.py` 🔧 CLAUDE (walked through)

For the joined strategy: read base rows, batch-resolve each configured
relationship via the connector lookup, pass resolved fields to the verbaliser.
Strategy selectable so the harness can build both.

### 6. Comparison harness — `scripts/compare_verbalisation.py` (split)

Builds **both** indexes into separate namespaces so both stay queryable, runs a
hand-labelled set of ~8–12 deliberately *relational* queries against each, and
prints **recall@5** side by side.
- ✍️ CHIDUBEM: the recall@5 calculation (the scoring math).
- 🔧 CLAUDE: the load / run / print scaffolding.
- Together: the query → expected-rows labels.

### 7. Query labels & relevance definition — data file (together)

For templated synthetic data, "relevant" is defined structurally: a query's
expected rows = tickets matching a known theme **and** a referenced attribute
(e.g. `plan = enterprise`). Pinned down when authoring the labels so recall@5 is
meaningful, not circular.

## Data flow

```
tickets + customers + products
   → Connector: base rows + batch-resolved referenced rows
   → Indexer: attach resolved relations per configured FK
   → Verbaliser: isolated (own columns) | joined (own + relations)
   → Embedder → pgvector (two namespaces)
   → Harness: relational queries → recall@5 per strategy (side by side)
```

## Testing

At least one test is **written by Chidubem** (hints only) — testing is the
self-named gap for this milestone.

- **Unit — joined verbaliser** (✍️ CHIDUBEM likely target): a row plus resolved
  relations produces the expected deterministic text, with labels, pulling only
  the configured descriptive columns.
- **Unit — recall@5**: known ranked ids vs. known expected ids → correct fraction;
  edge cases (no expected rows, expected row absent from top-5).
- **Unit — referenced-row lookup**: builds the `{key: row}` map for given keys;
  missing keys handled.
- No test requires a live database or embedding model (fakes / fixed inputs).

## Verification

1. `pytest`, `ruff check .`, `ruff format --check .`, `mypy src` all green.
2. Re-seed: `customers` and `products` populated; `support_tickets` FKs valid
   (a bad `customer_id` is rejected by the constraint).
3. Run the comparison harness → a side-by-side recall@5 table for isolated vs.
   joined on the relational query set.
4. The chosen strategy and its numbers are recorded (harness output + a note),
   so "I measured and chose on the data" is backed by an artifact.

## Deferred: one-to-many fan-out

Following a **one-to-many** relationship (e.g. a ticket's many `comments`) is the
natural next relationship problem and is **out of scope here**. It requires a rule
for how many child rows to include and how to summarise/truncate them so the text
does not explode and dilute the embedding. Punting keeps this milestone to two
clean many-to-one joins. Recorded as a Stretch item in `docs/ROADMAP.md`.

## Docs & artifacts

- This spec.
- `docs/ROADMAP.md`: add a one-to-many fan-out bullet under Stretch.
- ADR: "Explicit relationship config over DB introspection" — the read-only-
  middleware reasoning, for the interview record.
