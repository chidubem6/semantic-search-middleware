import pytest

from semantic_search_middleware.evaluation.recall import recall_at_k


def test_all_relevant_in_top_k():
    assert recall_at_k(["3", "1", "2", "9"], {"1", "2", "3"}, k=5) == 1.0


def test_partial_recall_counts_only_relevant_within_k():
    # relevant = {1,2,3}; top-3 window = [1,4,2] → found 2 of 3
    assert recall_at_k(["1", "4", "2", "3"], {"1", "2", "3"}, k=3) == pytest.approx(2 / 3)


def test_k_larger_than_results_is_fine():
    assert recall_at_k(["1"], {"1", "2"}, k=5) == pytest.approx(0.5)


def test_no_relevant_rows_defined_returns_zero_not_crash():
    assert recall_at_k(["1", "2"], set(), k=5) == 0.0
