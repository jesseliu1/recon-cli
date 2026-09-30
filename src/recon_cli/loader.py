"""Read a CSV file into a list of Record objects."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

REQUIRED_COLUMNS = ("id", "amount")


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
    except UnicodeDecodeError as exc:
        raise InputError(f"{path}: file is not valid UTF-8 ({exc.reason})") from exc


def _read(fh, path: Path) -> list[Record]:
    reader = csv.reader(fh)
    header = next(reader, None)
    if header is None:
        raise InputError(f"{path}: file is empty (a header row is required)")
    header = [name.strip() for name in header]
    for col in REQUIRED_COLUMNS:
        if col not in header:
            raise InputError(f"{path}:1: missing required column '{col}'")
    id_idx = header.index("id")
    amount_idx = header.index("amount")

    records: list[Record] = []
    while True:
        start_line = reader.line_num + 1
        row = next(reader, None)
        if row is None:
            break
        amount_text = row[amount_idx].strip()
        records.append(
            Record(
                id=row[id_idx].strip(),
                amount=Decimal(amount_text),
                amount_text=amount_text,
                line=start_line,
            )
        )
    return records
