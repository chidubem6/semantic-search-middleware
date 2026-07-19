from semantic_search_middleware.ingestion.verbaliser import RowVerbaliser


def test_verbaliser_is_deterministic() -> None:
    verbaliser = RowVerbaliser()
    row = {"id": 7, "status": "late", "customer": "Ada"}

    text = verbaliser.verbalise("orders", row, ["id", "status", "customer"])

    assert text == "Record from orders. id: 7; status: late; customer: Ada."
