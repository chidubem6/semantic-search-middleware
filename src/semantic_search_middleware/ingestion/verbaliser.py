from collections.abc import Mapping, Sequence
from typing import Any


class RowVerbaliser:
    """Deterministically converts selected fields from one row into text."""

    def verbalise(
        self,
        table: str,
        row: Mapping[str, Any],
        columns: Sequence[str],
        relations: Sequence[tuple[str, Mapping[str, Any]]] = (),
    ) -> str:
        fields = "; ".join(f"{column}: {row.get(column)}" for column in columns)

        relation_fields = ";".join(
            f" {label}: ({', '.join(fields.values())})" for label, fields in relations
        )

        return f"Record from {table}. {fields}.{relation_fields}"
