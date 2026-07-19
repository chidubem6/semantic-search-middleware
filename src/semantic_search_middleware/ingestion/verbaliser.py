from collections.abc import Mapping, Sequence
from typing import Any


class RowVerbaliser:
    """Deterministically converts selected fields from one row into text."""

    def verbalise(self, table: str, row: Mapping[str, Any], columns: Sequence[str]) -> str:
        fields = "; ".join(f"{column}: {row.get(column)}" for column in columns)
        return f"Record from {table}. {fields}."
