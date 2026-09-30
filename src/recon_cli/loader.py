"""Read a CSV file into a list of Record objects."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

REQUIRED_COLUMNS = ("id", "amount")

# Plain decimal notation only: no exponent, no separators, no NaN/Infinity.
_AMOUNT_RE = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)")


class InputError(Exception):
    """The input file cannot be used (bad shape, encoding, or values)."""


@dataclass(frozen=True)
class Record:
    id: str
    amount: Decimal
    amount_text: str
    line: int


def load_records(path: str | Path) -> list[Record]:
    path = Path(path)
    try:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            return _read(fh, path)
    except OSError as exc:
        raise InputError(f"{path}: cannot read file ({exc.strerror})") from exc
    except UnicodeDecodeError as exc:
        raise InputError(f"{path}: file is not valid UTF-8 ({exc.reason})") from exc


def _read(fh, path: Path) -> list[Record]:
    reader = csv.reader(fh)
    header = next(reader, None)
    if header is None:
        raise InputError(f"{path}: file is empty (a header row is required)")
    header = [name.strip() for name in header]
    seen_cols: set[str] = set()
    for name in header:
        if name in seen_cols:
            raise InputError(f"{path}:1: duplicate column '{name}'")
        seen_cols.add(name)
    for col in REQUIRED_COLUMNS:
        if col not in header:
            raise InputError(f"{path}:1: missing required column '{col}'")
    id_idx = header.index("id")
    amount_idx = header.index("amount")

    records: list[Record] = []
    first_seen: dict[str, int] = {}
    while True:
        start_line = reader.line_num + 1
        row = next(reader, None)
        if row is None:
            break
        if not row:  # completely blank line
            continue
        where = f"{path}:{start_line}"
        if len(row) != len(header):
            raise InputError(
                f"{where}: expected {len(header)} fields, found {len(row)}"
            )
        record_id = row[id_idx].strip()
        if not record_id:
            raise InputError(f"{where}: empty id")
        amount_text = row[amount_idx].strip()
        if not amount_text:
            raise InputError(f"{where}: empty amount for id '{record_id}'")
        if not _AMOUNT_RE.fullmatch(amount_text):
            raise InputError(
                f"{where}: invalid amount {amount_text!r} for id '{record_id}'"
            )
        if record_id in first_seen:
            raise InputError(
                f"{where}: duplicate id '{record_id}' "
                f"(first seen at line {first_seen[record_id]})"
            )
        first_seen[record_id] = start_line
        records.append(
            Record(
                id=record_id,
                amount=Decimal(amount_text),
                amount_text=amount_text,
                line=start_line,
            )
        )
    return records
