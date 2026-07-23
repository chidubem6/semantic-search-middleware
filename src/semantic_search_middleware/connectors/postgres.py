from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.engine import Engine


def index_rows_by_key(rows: Iterable[dict[str, Any]], key: str) -> dict[Any, dict[str, Any]]:
    """Turn a flat list of rows into a {key_value: row} lookup.

    Pure data-shaping, no database — this is the testable core of the batched
    referenced-row fetch below.
    """
    return {row[key]: dict(row) for row in rows}


class PostgresConnector:
    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(database_url)
        self._metadata = MetaData()

    def read_rows(self, table: str, columns: Sequence[str]) -> Iterable[dict[str, Any]]:
        reflected = Table(table, self._metadata, autoload_with=self._engine)
        selected_columns = [reflected.c[column] for column in columns]
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
        """Batch-fetch referenced rows for a relationship in ONE query.

        Given the key values collected from the base rows, run a single
        `WHERE key IN (...)` (not one query per row -- avoids the N+1 problem) and
        return a {key_value: {column: value}} lookup the indexer can join against.
        """
        wanted = list(dict.fromkeys(key_values))  # de-duplicate, preserve order
        if not wanted:
            return {}
        reflected = Table(table, self._metadata, autoload_with=self._engine)
        selected = [reflected.c[key], *[reflected.c[column] for column in columns]]
        stmt = select(*selected).where(reflected.c[key].in_(wanted))
        with self._engine.connect() as connection:
            rows = [dict(row) for row in connection.execute(stmt).mappings()]
        return index_rows_by_key(rows, key)
