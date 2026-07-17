from semantic_search_middleware.ingestion.verbalizer import RowVerbalizer


def test_verbalizer_is_deterministic() -> None:
    verbalizer = RowVerbalizer()
    row = {"id": 7, "status": "late", "customer": "Ada"}

    text = verbalizer.verbalize("orders", row, ["id", "status", "customer"])

    assert text == "Record from orders. id: 7; status: late; customer: Ada."
