from collections.abc import Sequence

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

    def index_table(self, table: str, primary_key: str, content_columns: Sequence[str]) -> int:
        documents = []
        texts = []

        # Fetch the content columns *plus* the primary key: the key is needed for the
        # document id and citation, but is deliberately kept out of the embedded text.
        for row in self._connector.read_rows(table, [*content_columns, primary_key]):
            text = self._verbaliser.verbalise(
                table, row, content_columns
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
