"""Compare two lists of records by id."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Context, Decimal

from recon_cli.loader import Record


@dataclass(frozen=True, slots=True)
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


def reconcile(
    records_a: list[Record],
    records_b: list[Record],
    tolerance: Decimal = Decimal(0),
) -> ReconResult:
    """Match records by id.

    Amounts within ``tolerance`` (inclusive) count as matched.
    """
    if not tolerance.is_finite() or tolerance < 0:
        raise ValueError(f"tolerance must be a finite number >= 0, got {tolerance}")
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
        else:
            difference = _exact_difference(a.amount, b.amount)
            if abs(difference) <= tolerance:
                result.matched.append(Item(id_, a.amount_text, b.amount_text))
            else:
                result.amount_mismatch.append(
                    Item(id_, a.amount_text, b.amount_text, difference)
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


def _exact_difference(a: Decimal, b: Decimal) -> Decimal:
    """b - a without the default 28-digit context rounding the result."""
    high = max(a.adjusted(), b.adjusted())
    low = min(a.as_tuple().exponent, b.as_tuple().exponent)
    return Context(prec=max(high - low + 2, 1)).subtract(b, a)
