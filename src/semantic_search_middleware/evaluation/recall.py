"""Recall@k retrieval metric.

Computes the fraction of relevant rows that appear in the top-k retrieved results.
A pure scoring helper in the `evaluation/` layer, used to measure retrieval quality
against a labelled dataset.
"""


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:

    if not relevant:
        return 0.0

    top_hits = retrieved[:k]

    relevant_count = len(relevant.intersection(top_hits))

    return relevant_count / len(relevant)
