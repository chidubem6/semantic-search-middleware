from collections.abc import Iterable
from typing import Any

import pytest

from semantic_search_middleware.config.settings import Relationship, get_settings
from semantic_search_middleware.domain.models import SearchResult
from semantic_search_middleware.embeddings.sentence_transformer import SentenceTransformerEmbedder
from semantic_search_middleware.evaluation.recall import recall_at_k
from semantic_search_middleware.ingestion.indexer import IndexingService
from semantic_search_middleware.ingestion.verbaliser import RowVerbaliser

# Controlled fixture data for the isolated-vs-joined comparison harness.
#
# The gold ticket (id 1) is a *discriminator*: its own text says nothing about
# the customer's plan or region, so the query below can only reach it once the
# "joined" strategy folds Ada's gold/EU fields into the embedded text. The two
# distractors point at a non-gold customer, so recall has wrong answers to reject.

support_tickets = [
    # GOLD — plain login body, but its customer is gold/EU
    {
        "id": 1,
        "subject": "Cannot log in after password reset",
        "body": (
            "the user completed a password reset but the new password is "
            "rejected on the login screen"
        ),
        "product": "Mobile",
        "status": "Unsolved",
        "priority": "High",
        "customer_id": 1,
        "product_id": 20,
    },
    # DISTRACTOR — non-gold customer
    {
        "id": 2,
        "subject": "App crashes when exporting a report to PDF",
        "body": (
            "the mobile app closes unexpectedly while generating a PDF export of a monthly report"
        ),
        "product": "Mobile",
        "status": "Open",
        "priority": "Low",
        "customer_id": 2,
        "product_id": 20,
    },
    # DISTRACTOR — non-gold customer
    {
        "id": 3,
        "subject": "Push notifications arrive late",
        "body": (
            "notifications on the mobile app are delayed by several hours "
            "compared to the web version"
        ),
        "product": "Mobile",
        "status": "Open",
        "priority": "Low",
        "customer_id": 2,
        "product_id": 20,
    },
]

# Raw rows, as a real connector would hand them back: a flat list, each row
# carrying its own "id". read_referenced_rows keys these by id itself.
customers = [
    {"id": 1, "name": "Ada Okafor", "plan": "gold", "region": "EU"},
    {"id": 2, "name": "Bright Mensah", "plan": "free", "region": "US"},
]

products = [
    {"id": 20, "name": "Mobile", "team": "Mobile Development"},
]

# Each query paired with the document_ids that count as correct answers.
queries = [
    ("issues from gold-plan customers in the EU", {"support_tickets:1"}),
]

# Passed to BOTH indexing runs. The isolated run is handed these and declines to
# use them because of its strategy flag -- so strategy is the only variable.
relationships = [
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
        columns=["name", "team"],
        label="product",
    ),
]


def index_rows_by_key(rows: Iterable[dict[str, Any]], key: str) -> dict[Any, dict[str, Any]]:
    return {row[key]: row for row in rows}

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Output: a score ranging from -1 (opposite) to 1 (identical), with 0
    indicating orthogonality. i.e 0.94
    Input: two vectors as lists of floats. i.e a = [0.4, 0.2, 0.3], b = [0.3, 0.5, 0.1]

    if vectors are not the same length, raise a ValueError?.
    for each position of the vector, multiply the two values together and sum
    them up to get the dot product.

    Return the cosine similarity between two vectors.

    Cosine similarity is the cosine of the angle between two vectors, which is
    equivalent to their dot product divided by the product of their magnitudes.
    It ranges from -1 (opposite) to 1 (identical), with 0 indicating orthogonality.

    Args:
        vec_a: First vector as a list of floats.
        vec_b: Second vector as a list of floats.
    """

    if len(vec_a) != len(vec_b):
        raise ValueError("Vectors must be of the same length.")

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
    magnitude_a = sum(a ** 2 for a in vec_a) ** 0.5
    magnitude_b = sum(b ** 2 for b in vec_b) ** 0.5

    if magnitude_a == 0 or magnitude_b == 0:
        raise ValueError("One or both vectors have zero magnitude.")

    return dot_product / (magnitude_a * magnitude_b)


# --- yours to write from here ---
class FakeConnector:
    def __init__(self):
        self._support_tickets = support_tickets
        self._customers = customers
        self._products = products

    def read_rows(self, table, columns):
        """
        Output: support tickets list.

        Input: string table name, e.g. "support_tickets"

        Read the string. Return the corresponding list of dictionaries for that table.

        `columns` is accepted to match the RelationalConnector port, but deliberately
        ignored: the verbaliser selects the fields it wants itself, so extra keys on
        these rows can never reach the embedded text.
        """

        if table == "support_tickets":
            return self._support_tickets
        else:
            raise ValueError(f"Unknown table: {table}")
    

    def read_referenced_rows(self, table, key, key_values, columns):
        """
        Return {key_value: {column: value, ...}, ...} for the requested key_values.

        Input: table name, the key column, the key values to retrieve, and the
        columns to return. For example:

            read_referenced_rows("customers", "id", [1, 2, 2], ["plan", "region"])

        against

            customers = [
                {"id": 1, "name": "Ada Okafor", "plan": "gold", "region": "EU"},
                {"id": 2, "name": "Bright Mensah", "plan": "free", "region": "US"},
            ]

        returns

            {
                1: {"id": 1, "plan": "gold", "region": "EU"},
                2: {"id": 2, "plan": "free", "region": "US"},
            }

        Note the shape, which mirrors PostgresConnector exactly:
          - duplicate key_values collapse (three tickets, two customers);
          - "name" is absent, because it was not requested;
          - "id" is present even though it was not in `columns`, because the real
            SELECT puts the key column first. index_rows_by_key needs it too.
        """

        wanted = list(dict.fromkeys(key_values))  # deduplicate, preserve order

        if not wanted:
            return {}

        if table == "customers":
            source_rows = self._customers
        elif table == "products":
            source_rows = self._products
        else:
            raise ValueError(f"Unknown table: {table}")

        matching_rows = [row for row in source_rows if row[key] in wanted]

        trimmed_rows = [
            {column: row[column] for column in (key, *columns)} for row in matching_rows
        ]

        return index_rows_by_key(trimmed_rows, key)


class FakeVectorStore:
    def __init__(self, min_similarity_score: float = 0.0):
        self.documents = []
        self.vectors = []
        # Matches below this score are dropped in search(), same as PgVectorStore.
        # Default 0.0 keeps every non-negative match, so the distractors still show
        # up in the ranking and recall has wrong answers to rank below the gold one.
        self._min_similarity_score = min_similarity_score

    def upsert(self, documents, vectors):
        if len(documents) != len(vectors):
            raise ValueError("Documents and vectors must have the same length.")
        
        self.documents.extend(documents)
        self.vectors.extend(vectors)

    def search(self, query_vector, top_k, filters=None):
        """
        returned a list of search results, sorted by score descending, with a
        maximum length of top_k.

        Search Results = document, score
        document = document_id, text, source (table, primary_key, primary_key_value)

        Output: a list of search results, sorted by score descending, with a
        maximum length of top_k.
        i.e SearchResult(IndexedDocument1, 0.95), SearchResult(IndexedDocument2, 0.90), ...)

        Input: query_vector = [0.1, 0.2, 0.3], top_k = 5, filters = None

        for each document in the store,
        compute the cosine similarity between the query_vector and the document's vector.
        return the top_k documents with the highest similarity scores, sorted in descending order.
        """

        rows = zip(self.documents, self.vectors, strict=True)
        results = []

        for document, vector in rows:
            score = cosine_similarity(query_vector, vector)

            if score < self._min_similarity_score:
                continue

            results.append(SearchResult(document=document, score=score))

        return sorted(results, key=lambda result: result.score, reverse=True)[:top_k]




@pytest.fixture(scope="module")
def embedder():
    """Load the transformer once for the whole file, not once per test.

    Stateless and read-only, so sharing it across tests is safe -- and it is the
    slow collaborator here (a few seconds of model load on first use).
    """
    return SentenceTransformerEmbedder(get_settings().embedding_model)


def test_joined_strategy_beats_isolated_on_recall(embedder):
    # --- Arrange ----------------------------------------------------------
    # Fresh stores per test: they accumulate documents, so sharing them would
    # leak one test's index into the next. The embedder can be shared; these
    # cannot. Both runs use the same embedder -- same model, same weights.
    isolated_store = FakeVectorStore()
    joined_store = FakeVectorStore()

    # Anonymous, because nothing below refers to them again.
    isolated_indexer = IndexingService(
        FakeConnector(), RowVerbaliser(), embedder, isolated_store
    )
    joined_indexer = IndexingService(
        FakeConnector(), RowVerbaliser(), embedder, joined_store
    )

    content_columns = ["subject", "body", "product", "status", "priority"]

    # --- Act --------------------------------------------------------------
    isolated_indexer.index_table(
        "support_tickets",
        "id",
        content_columns,
        relationships=relationships,
        strategy="isolated",
    )

    joined_indexer.index_table(
        "support_tickets",
        "id",
        content_columns,
        relationships=relationships,
        strategy="joined",
    )

    # --- Assert -----------------------------------------------------------
    for query, expected_ids in queries:
        query_vector = embedder.embed([query])[0]

        isolated_results = isolated_store.search(query_vector, top_k=5)
        joined_results = joined_store.search(query_vector, top_k=5)

        isolated_ids = [result.document.document_id for result in isolated_results]
        joined_ids = [result.document.document_id for result in joined_results]

        isolated_recall = recall_at_k(retrieved=isolated_ids, relevant=expected_ids, k=1)
        joined_recall = recall_at_k(retrieved=joined_ids, relevant=expected_ids, k=1)

        # Printed, not asserted: the exact figures are the measurement and belong
        # in the ADR. Run with `pytest -s` to see them. The assert below guards the
        # claim, which must hold even if the numbers move.
        print(f"\nquery: {query!r}")
        print(f"  recall@1  isolated={isolated_recall}  joined={joined_recall}")
        print(f"  isolated ranking: {isolated_ids}")
        print(f"  joined   ranking: {joined_ids}")

        assert joined_recall > isolated_recall, (
            f"Folding related fields in did not improve recall for {query!r}. "
            f"recall@1 isolated={isolated_recall} joined={joined_recall}; "
            f"isolated ranking={isolated_ids}, joined ranking={joined_ids}"
        )
