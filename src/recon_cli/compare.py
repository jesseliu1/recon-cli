"""Compare two lists of records by id."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from recon_cli.loader import Record


@dataclass(frozen=True)
class Item:
    id: str
    amount_a: str | None = None
    amount_b: str | None = None
    difference: Decimal | None = None


@dataclass
class ReconResult:
    matched: list[Item] = field(default_factory=list)
    missing_in_a: list[Item] = field(default_factory=list)
    missing_in_b: list[Item] = field(default_factory=list)
    amount_mismatch: list[Item] = field(default_factory=list)

    @property
    def has_differences(self) -> bool:
        return bool(self.missing_in_a or self.missing_in_b or self.amount_mismatch)


def reconcile(records_a: list[Record], records_b: list[Record]) -> ReconResult:
    by_id_a = _index(records_a, "A")
    by_id_b = _index(records_b, "B")
    result = ReconResult()

    for id_ in sorted(by_id_a.keys() | by_id_b.keys()):
        a = by_id_a.get(id_)
        b = by_id_b.get(id_)
        if b is None:
            result.missing_in_b.append(Item(id_, amount_a=a.amount_text))
        elif a is None:
            result.missing_in_a.append(Item(id_, amount_b=b.amount_text))
        elif a.amount == b.amount:
            result.matched.append(Item(id_, a.amount_text, b.amount_text))
        else:
            result.amount_mismatch.append(
                Item(id_, a.amount_text, b.amount_text, b.amount - a.amount)
            )
    return result


def _index(records: list[Record], side: str) -> dict[str, Record]:
    # load_records already rejects duplicates; guard here so a caller that
    # builds records by hand cannot get silent "last one wins" behaviour.
    index: dict[str, Record] = {}
    for r in records:
        if r.id in index:
            raise ValueError(f"duplicate id {r.id!r} in input {side}")
        index[r.id] = r
    return index
