"""sentence-transformers embedding backend.

Adapts a local sentence-transformers model to the Embedder port, encoding text
into normalised vectors. This is the embeddings adapter at the Embedder stage of
the ingestion pipeline (Verbaliser -> Embedder -> pgvector).
"""

from collections.abc import Sequence
from typing import cast

from sentence_transformers import SentenceTransformer


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str) -> None:
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        # .tolist() is untyped (returns Any); cast to the declared return type.
        return cast(list[list[float]], vectors.tolist())
