"""PostgreSQL relational connector.

SQLAlchemy-backed adapter that reads rows from a source table and fetches
related rows by key for relationship-aware verbalisation. The connector stage of
the pipeline (`PostgreSQL -> Connector -> ...`), implementing the
`RelationalConnector` port over the source database.
"""

from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.engine import Engine


class PostgresConnector:
    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(database_url)
        self._metadata = MetaData()

    def read_rows(self, table: str, columns: Sequence[str]) -> Iterable[dict[str, Any]]:
        referenced_table = Table(table, self._metadata, autoload_with=self._engine)
        selected_columns = [referenced_table.c[column] for column in columns]
        with self._engine.connect() as connection:
            for row in connection.execute(select(*selected_columns)).mappings():
                yield dict(row)

    def read_referenced_rows(
        self,
        table: str,
        key: str,
        key_values: Iterable[Any],
        columns: Sequence[str],
    ) -> dict[Any, dict[str, Any]]:
        referenced_table = Table(table, self._metadata, autoload_with=self._engine)
        selected_columns = [referenced_table.c[c] for c in columns]

        wanted = list(dict.fromkeys(key_values))

        if not wanted:
            return {}

        condition = referenced_table.c[key].in_(wanted)
        statement = select(referenced_table.c[key], *selected_columns).where(condition)

        with self._engine.connect() as connection:
            result = [dict(rows) for rows in connection.execute(statement).mappings()]

        return index_rows_by_key(result, key)


def index_rows_by_key(rows: Iterable[dict[str, Any]], key: str) -> dict[Any, dict[str, Any]]:
    return {row[key]: row for row in rows}
