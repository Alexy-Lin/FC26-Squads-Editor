from dataclasses import dataclass
from typing import Any, Iterator, List, Union


@dataclass(frozen=True)
class FieldChange:
    table: str
    key_field: str
    key_value: int
    field: str
    old_value: Any
    new_value: Any


@dataclass(frozen=True)
class RecordChange:
    table: str
    key_field: str
    key_value: int
    action: str
    record: dict[str, Any]
    index: int


Change = Union[FieldChange, RecordChange]


class ChangeSet:
    def __init__(self):
        self._changes: List[Change] = []

    def add(self, change: Change):
        self._changes.append(change)

    def extend(self, changes):
        self._changes.extend(changes)

    def rollback(self, sav):
        for change in reversed(self._changes):
            table = sav.db.get_table(change.table)
            if isinstance(change, FieldChange):
                record = next(
                    r for r in table.records
                    if r.get(change.key_field) == change.key_value
                )
                record[change.field] = change.old_value
            elif change.action == "add":
                table.records[:] = [
                    r for r in table.records
                    if r.get(change.key_field) != change.key_value
                ]
                table.n_valid_records = len(table.records)
            else:
                table.records.insert(change.index, dict(change.record))
                table.n_valid_records = len(table.records)

    def __iter__(self) -> Iterator[Change]:
        return iter(self._changes)

    def __len__(self):
        return len(self._changes)
