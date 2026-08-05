def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:

    if not relevant:
        return 0.0

    top_hits = retrieved[:k]

    relevant_count = len(relevant.intersection(top_hits))

    return relevant_count / len(relevant)
