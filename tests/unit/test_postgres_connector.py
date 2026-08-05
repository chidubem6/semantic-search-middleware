from semantic_search_middleware.connectors.postgres import index_rows_by_key


def test_index_rows_by_key_builds_lookup_keyed_on_the_key_column() -> None:
    rows = [
        {"id": 1, "name": "Ada", "plan": "enterprise"},
        {"id": 2, "name": "Blake", "plan": "free"},
    ]

    lookup = index_rows_by_key(rows, "id")

    assert lookup == {
        1: {"id": 1, "name": "Ada", "plan": "enterprise"},
        2: {"id": 2, "name": "Blake", "plan": "free"},
    }


def test_index_rows_by_key_handles_no_rows() -> None:
    assert index_rows_by_key([], "id") == {}
