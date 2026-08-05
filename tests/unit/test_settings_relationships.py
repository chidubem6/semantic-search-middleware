"""Tests the configuration the strategy comparison depends on.

Asserts that no relationship requests a column already indexed on the base table
(so the isolated strategy cannot reach it), and that the customer relationship
does request the fields the comparison relies on.
"""

from semantic_search_middleware.config import get_settings


def test_no_relationship_column_is_also_a_base_column() -> None:
    """The isolated strategy must not be able to reach a relationship's fields.

    If a column appears in both lists, both strategies embed it and the
    isolated-vs-joined comparison stops measuring anything -- silently, because
    nothing about the configuration looks wrong.
    """
    settings = get_settings()

    relationship_columns = set()

    for relationship in settings.index_relationships:
        relationship_columns.update(relationship.columns)

    shared_columns = relationship_columns & set(settings.index_columns)

    assert not shared_columns, f"reachable without a join: {shared_columns}"


def test_customer_plan_and_region_are_requested_by_the_join() -> None:
    """The other half: the joined strategy must actually ask for those fields.

    Their absence from index_columns only proves the isolated strategy cannot
    reach them. This proves the joined strategy does.
    """
    settings = get_settings()

    customer = None

    for relationship in settings.index_relationships:
        if relationship.label == "customer":
            customer = relationship
            break

    assert customer is not None, "no relationship labelled 'customer' is configured"
    assert {"plan", "region"}.issubset(customer.columns)
