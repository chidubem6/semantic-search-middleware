"""pgvector-backed VectorStore implementation.

This is the physical shape of the "index": a `documents` table where each row is
one indexed record — its text, its embedding (a vector column), and a pointer
back to the source row for citations.
"""

from collections.abc import Sequence
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, MetaData, Table, Text, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from semantic_search_middleware.domain.models import (
    IndexedDocument,
    SearchResult,
    SourceReference,
)


class PgVectorStore:
    def __init__(
        self,
        database_url: str,
        embedding_dimension: int,
        min_similarity_score: float = 0.0,
    ) -> None:
        self._engine: Engine = create_engine(database_url)
        self._metadata = MetaData()
        # Matches below this score are dropped in search() as not relevant enough.
        self._min_similarity_score = min_similarity_score
        # The index table. `embedding` is the special pgvector column that holds
        # all `embedding_dimension` (384) numbers in one cell and can measure
        # closeness between vectors. The source_* columns point back to the
        # original row so results can be cited.
        self._documents = Table(
            "documents",
            self._metadata,
            Column("document_id", Text, primary_key=True),
            Column("content", Text, nullable=False),
            Column("embedding", Vector(embedding_dimension), nullable=False),
            Column("source_table", Text, nullable=False),
            Column("source_pk", Text, nullable=False),
            Column("source_pk_value", Text, nullable=False),
            Column("doc_metadata", JSONB, nullable=False),
        )
        # Create the table on first use if it does not exist yet.
        self._metadata.create_all(self._engine)

    def upsert(self, documents: Sequence[IndexedDocument], vectors: Sequence[list[float]]) -> None:
        """Insert documents, or update them if the document_id already exists.

        Idempotent: re-indexing the same rows overwrites them instead of creating
        duplicates (because document_id is deterministic, e.g. "support_tickets:1").
        """
        rows = [
            {
                "document_id": doc.document_id,
                "content": doc.text,
                "embedding": vector,
                "source_table": doc.source.table,
                "source_pk": doc.source.primary_key,
                "source_pk_value": doc.source.primary_key_value,
                "doc_metadata": doc.metadata,
            }
            for doc, vector in zip(documents, vectors, strict=True)
        ]
        if not rows:
            return

        stmt = pg_insert(self._documents).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["document_id"],
            set_={
                "content": stmt.excluded.content,
                "embedding": stmt.excluded.embedding,
                "source_table": stmt.excluded.source_table,
                "source_pk": stmt.excluded.source_pk,
                "source_pk_value": stmt.excluded.source_pk_value,
                "doc_metadata": stmt.excluded.doc_metadata,
            },
        )
        with self._engine.begin() as connection:
            connection.execute(stmt)

    def search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        # Cosine distance (pgvector <=>) from the query to every stored embedding.
        distance = self._documents.c.embedding.cosine_distance(query_vector)

        stmt = select(self._documents, distance.label("distance")).order_by(distance).limit(top_k)

        results: list[SearchResult] = []

        with self._engine.connect() as connection:
            rows = connection.execute(stmt).mappings().all()

            for row in rows:
                score = 1 - row["distance"]  # Convert distance to similarity score

                if score < self._min_similarity_score:
                    continue

                results.append(
                    SearchResult(
                        document=IndexedDocument(
                            document_id=row["document_id"],
                            text=row["content"],
                            source=SourceReference(
                                table=row["source_table"],
                                primary_key=row["source_pk"],
                                primary_key_value=row["source_pk_value"],
                            ),
                            metadata=row["doc_metadata"],
                        ),
                        score=score,
                    )
                )

        return results
