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

        # str() every value: related columns can be ints, bools or None, and
        # join() only accepts strings. The f-string above does this implicitly.
        relation_fields = ";".join(
            f" {label}: ({', '.join(str(value) for value in related_row.values())})"
            for label, related_row in relations
        )

        return f"Record from {table}. {fields}.{relation_fields}"
