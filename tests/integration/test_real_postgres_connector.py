import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from semantic_search_middleware.config import get_settings
from semantic_search_middleware.connectors.postgres import PostgresConnector


@pytest.fixture
def source_connector() -> PostgresConnector:
    """A connector against the seeded source database, or skip if it is not up.

    Cloning the repo without running docker should report "skipped", not a wall
    of failures for a database that was never expected to be there.
    """
    url = get_settings().source_database_url

    # connect_timeout is essential, not tidiness: without it psycopg waits
    # indefinitely on an unreachable host, so the guard hangs instead of skipping.
    try:
        create_engine(url, connect_args={"connect_timeout": 2}).connect().close()
    except OperationalError:
        pytest.skip("source database unreachable -- start it with `docker compose up -d`")

    return PostgresConnector(url)


def test_read_referenced_rows_returns_the_shape_our_fakes_assume(
    source_connector: PostgresConnector,
) -> None:
    referenced_rows = source_connector.read_referenced_rows("customers", "id", [1, 1, 1], ["plan"])

    assert referenced_rows == {1: {"id": 1, "plan": "free"}}
