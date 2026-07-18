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
