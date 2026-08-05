"""Indexing use case that builds and stores the embedding index.

Orchestrates the full ingestion pipeline: reads source rows via the connector,
optionally resolves declared foreign-key relationships in batched queries (the
"joined" strategy, avoiding N+1), verbalises each row, embeds the text, and
upserts the resulting documents into the vector store. This is the application
service layer wiring the connector, verbaliser, embedder, and vector-store ports.
"""

from collections.abc import Sequence

from semantic_search_middleware.config.settings import Relationship
from semantic_search_middleware.domain.models import IndexedDocument, SourceReference
from semantic_search_middleware.domain.ports import Embedder, RelationalConnector, VectorStore
from semantic_search_middleware.ingestion.verbaliser import RowVerbaliser


class IndexingService:
    def __init__(
        self,
        connector: RelationalConnector,
        verbaliser: RowVerbaliser,
        embedder: Embedder,
        vector_store: VectorStore,
    ) -> None:
        self._connector = connector
        self._verbaliser = verbaliser
        self._embedder = embedder
        self._vector_store = vector_store

    def index_table(
        self,
        table: str,
        primary_key: str,
        content_columns: Sequence[str],
        relationships: Sequence[Relationship] = (),
        strategy: str = "isolated",
    ) -> int:
        documents = []
        texts = []

        rows = list(
            self._connector.read_rows(
                table, [primary_key, *content_columns, *[rel.local_column for rel in relationships]]
            )
        )

        # Resolved referenced rows, keyed {local_column: {key_value: fields}} -- e.g.
        # {"customer_id": {7: {"name": "Ada", "plan": "enterprise", ...}}}.
        foreign_key_dict = {}

        # Resolve every relationship up front in ONE batch query each (not per row --
        # avoids the N+1 problem). Only the "joined" strategy pulls related data.
        if strategy == "joined":
            for rel in relationships:
                key_values = [row[rel.local_column] for row in rows]  # this rel's FK on every row

                referenced_rows_by_keys = self._connector.read_referenced_rows(
                    rel.referenced_table, rel.referenced_key, key_values, rel.columns
                )

                foreign_key_dict[rel.local_column] = referenced_rows_by_keys

        for row in rows:
            # Fold each relationship's fields for THIS row into (label, fields) pairs.
            relations = []
            if strategy == "joined":
                for rel in relationships:
                    # Look up this row's referenced record: its compartment, then its FK value.
                    referenced_row = foreign_key_dict[rel.local_column][row[rel.local_column]]

                    # Keep only the columns this relationship declared. The connector
                    # also returns the key column (its SELECT puts it first), and a
                    # join key is an accident of storage -- noise in embedded text.
                    fields = {column: referenced_row[column] for column in rel.columns}
                    relations.append((rel.label, fields))

            text = self._verbaliser.verbalise(
                table, row, content_columns, relations
            )  # Converts row into a standard format
            pk_value = str(row[primary_key])  # id of the row

            texts.append(text)  # list of standardised records
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

        vectors = self._embedder.embed(texts)  # gives an embedding to each row
        self._vector_store.upsert(
            documents, vectors
        )  # Adds / updates documents table with row and embedding

        return len(documents)
