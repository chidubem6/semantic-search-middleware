from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.engine import Engine


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
