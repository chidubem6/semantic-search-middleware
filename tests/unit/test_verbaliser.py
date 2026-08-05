from semantic_search_middleware.ingestion.verbaliser import RowVerbaliser


def test_verbaliser_is_deterministic() -> None:
    verbaliser = RowVerbaliser()
    row = {"id": 7, "status": "late", "customer": "Ada"}

    text = verbaliser.verbalise("orders", row, ["id", "status", "customer"])

    assert text == "Record from orders. id: 7; status: late; customer: Ada."


def test_no_relations_gives_isolated_test() -> None:
    verbaliser = RowVerbaliser()

    row = {"id": 7, "status": "late", "customer": "Ada"}

    verbalised_row = verbaliser.verbalise("orders", row, ["status", "customer"])

    assert verbalised_row == "Record from orders. status: late; customer: Ada."


def test_relations_are_folded_into_text() -> None:
    verbaliser = RowVerbaliser()

    row = {"id": 15, "item": "Blue Ceramic Mug"}

    relations = [
        ("Customer", {"name": "Zoe", "tier": "gold", "city": "Berlin"}),
        ("Warehouse", {"name": "West Depot", "region": "EU"}),
    ]

    text = verbaliser.verbalise("orders", row, ["item"], relations)

    for label, fields in relations:
        assert label in text
        for value in fields.values():
            assert value in text

    assert "15" not in text
