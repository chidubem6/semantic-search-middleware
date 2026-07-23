""" """

from semantic_search_middleware.config import get_settings


def test_index_relationship_fields_are_reachable_only_via_join() -> None:

    settings = get_settings()

    relationship_count = len(settings.index_relationships)

    """

    relationship_columns = []

    for relation in settings.index_relationships:
        if relation.label == "customer":
            for column in relation.columns:
                relationship_columns.append(column)
    """

    customer = [
        relation for relation in settings.index_relationships if relation.label == "customer"
    ][0]

    assert relationship_count == 2
    assert "plan" not in settings.index_columns
    assert "region" not in settings.index_columns
    assert "plan" in customer.columns and "region" in customer.columns
