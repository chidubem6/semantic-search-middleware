# ADR 0002: Fold related rows into the verbalised text before embedding

## Status
Accepted for Milestone 2. Extends ADR 0001; supersedes nothing.

## Context
Milestone 0 verbalised and embedded one table's own columns. That answers questions
phrased in the row's own words, but not questions about what the row is *related* to,
because the answer lives in another table and never reaches the embedded text.

A concrete failure: the query "issues from gold-plan customers in the EU" cannot reach a
ticket whose subject and body are about a password reset. The plan and the region are
columns of `customers`, not of `support_tickets`. Indexed in isolation, that ticket
ranked last of three (recall@1 = 0.0).

Two alternatives were considered.

**Index each table separately and combine at query time.** The join still has to happen;
this only moves it later, into retrieval code we would have to write, and it has to
operate on ranked result sets rather than on keys.

**Leave rows isolated and let the LLM assemble the context while generating.** Retrieval
would never surface the ticket in the first place, so generation has nothing to ground
on. That raises the risk of a hallucinated answer rather than lowering it.

## Decision
When indexing a row, also fold in the declared columns of the rows it references, and
embed the combined text.

Which relationships to follow — local column, referenced table and key, the columns to
pull, and a label — is declared in `Settings.index_relationships`. `IndexingService`
resolves them and `RowVerbaliser` renders them alongside the row's own fields.

The behaviour is a strategy flag on `index_table`, supplied by `Settings.index_strategy`
and typed `Literal["isolated", "joined"]` so a typo fails at startup rather than falling
through to an isolated index. `isolated` remains the default, so both paths stay runnable
and directly comparable and pulling this change does not reshape an existing index.

## Consequences

### Measured
On the fixture in `tests/unit/test_joined_vs_isolated_recall.py`, with
`all-MiniLM-L6-v2`, three rows and one query:

| strategy | recall@1 | ranking of the relevant row |
| --- | --- | --- |
| isolated | 0.0 | 3rd of 3 |
| joined | 1.0 | 1st of 3 |

This is one query against three rows on one model. It supports the direction of the
effect, not its magnitude, and the fixture was built to make the difference visible. No
claim about how much retrieval improves should rest on it. Milestone 5 replaces this with
30-50 questions and expected rows; these figures stand in until then.

### Observed on the full index
The fixture result did not carry over to 400 seeded rows indexed with the joined
strategy. Queried through `/api/v1/search`:

| query | top score | top hit's folded-in fields |
| --- | --- | --- |
| "enterprise plan customers in the EU" | 0.300 | `(Emeka, pro, APAC)` — wrong plan, wrong region |
| "gold plan customers in the EU" | 0.270 | dropped entirely by `MIN_SIMILARITY_SCORE=0.30` |
| "password reset not working" | 0.600 | correct, and the strongest match by far |

Folding the fields in is necessary but not sufficient. It makes the values *present* —
under the isolated strategy no query could reach them at all — but presence does not make
them *decisive*. Cosine similarity compares whole texts, and a short related-fields tail
barely moves the vector when 400 tickets are otherwise alike. The fixture showed a clean
result partly because the folded-in fields were a large share of a short text with only
two competitors.

Not measured: the same queries against an isolated index of the same 400 rows. The words
are absent there, so it should be worse, but that has not been run.

This is the concrete case for Milestone 3. Lexical matching privileges the literal token
"enterprise" in a way vector similarity does not, and attribute-shaped questions may be
better served by a structured filter than by retrieval at all — `SearchRequest.filters`
exists and is unused.

### Gained
- Questions about a row's relationships become answerable, because the answer is now in
  the embedded text rather than in a table retrieval never reads.
- Generation has something to ground on. Under the isolated strategy the relevant row is
  never retrieved, so the LLM is left to fill the gap itself.
- Both strategies stay runnable, so the comparison can be repeated whenever the model,
  the columns or the fixture change.

### Given up
- **Staleness, amplified by fan-out.** One `UPDATE` to a referenced row invalidates every
  document that folded it in: change one customer's plan and all of their tickets are
  wrong. The index is a copy, and copies drift.
- **The drift is silent.** Nothing errors and no test fails; the source database is
  correct and the index simply disagrees with it. The only symptom is a search that
  quietly stops returning rows it should. Milestone 4 bounds this rather than removing
  it: any index that is a copy is behind by however long since the last sync, and closing
  that window entirely would need writes we do not have on the source database.
- **Change detection must cover every table a document was built from.** This is a
  requirement the decision creates, and Milestone 4 as currently specified does not meet
  it. Its checksum covers the indexed row, but a customer's plan changing leaves every
  referencing ticket row byte-identical, so those documents are skipped as unchanged and
  keep the old value indefinitely. Indexing follows foreign keys forwards; invalidation
  has to follow them backwards, and nothing in the index records the dependency — the
  relationship is consumed at index time and only its output is kept. Two ways out:
  checksum the verbalised text rather than the source row, since that string contains the
  joined fields by construction; or record the referenced keys in each document's
  `metadata`, which exists and is unused, so a document states what it depends on.
- **Precision, in exchange for recall.** Every ticket belonging to one customer now
  carries the same customer text, which makes those tickets more similar to each other
  and lets a query match on the folded-in fields alone. Only recall was measured here, so
  the side of the trade that flatters the decision is the side with evidence.
- **Embedded text is longer, against a fixed input limit.** `all-MiniLM-L6-v2` reads at
  most 256 tokens and silently discards the rest. The verbaliser appends related fields
  last, so anything folded in is the first thing lost — the feature would stop working
  for long rows while continuing to work for short ones, with nothing to indicate it.
  Measured on the current index: longest document 339 characters, about 78 tokens, so
  roughly a third of the budget. Not a present problem; one to re-measure as ticket
  bodies grow or relationships are added.
- **Redundancy is easy to introduce and invisible in configuration.** The product
  relationship originally fetched `name`, which the ticket's own `product` column already
  carried, so every document embedded the product name twice. Nothing detected it: the
  column names differ (`name` against `product`), so no configuration check can see it,
  and it was found only by reading indexed text. The relationship now fetches the team
  alone, labelled `product team`, since the label has to carry the meaning the verbaliser
  drops when it renders values without their column names.

### Implementation notes
- Relationships are resolved in one batched query each, not one per row. The naive shape
  costs `1 + rows × relationships` round trips — over 20,000 for 10,000 tickets and two
  relationships — against three here, independent of table size.
- The referenced key column is dropped before verbalisation. A surrogate key carries no
  meaning for an embedding model, and the connector returns it only because its `SELECT`
  puts the key first. This changed no measured outcome and was made on principle.
- Filtering to the declared columns happens in `IndexingService`: the connector should
  report what SQL returned, and `RowVerbaliser` cannot distinguish a key from any other
  entry in a mapping.

### Testing
Every test of this path replaced the connector with a fake, which meant they all proved
the same conditional — given the rows we believe Postgres returns, the rest works — and
nothing checked the belief. That hid a real defect: the fake omitted the key column the
real `SELECT` returns, so an integer reached a `join()` over the related values and
raised `TypeError` the first time the joined path met a real database.

`tests/integration/test_real_postgres_connector.py` now pins the contract those fakes
copy, against the running database. A configuration test additionally asserts that no
relationship requests a column already in `index_columns`, because adding one would let
the isolated strategy reach the joined fields and invalidate every measurement here
without failing anything.
