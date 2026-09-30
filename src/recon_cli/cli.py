"""Command line entry point.

Exit codes: 0 = no differences, 1 = differences found, 2 = input or usage error.
"""

from __future__ import annotations

import argparse
import re
import sys
from decimal import Decimal

from recon_cli.compare import reconcile
from recon_cli.loader import InputError, load_records
from recon_cli.report import FORMATS, format_result

EXIT_OK = 0
EXIT_DIFFERENCES = 1
EXIT_ERROR = 2

_NUMBER_RE = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)")


def _tolerance(text: str) -> Decimal:
    if not _NUMBER_RE.fullmatch(text.strip()):
        raise argparse.ArgumentTypeError(f"invalid tolerance {text!r}: expected a decimal number")
    value = Decimal(text.strip())
    if value < 0:
        raise argparse.ArgumentTypeError(f"invalid tolerance {text!r}: must be >= 0")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recon-cli",
        description="Reconcile two CSV files (columns: id, amount) by id.",
    )
    parser.add_argument("file_a", help="first CSV file (A), e.g. ledger.csv")
    parser.add_argument("file_b", help="second CSV file (B), e.g. bank.csv")
    parser.add_argument(
        "--tolerance", type=_tolerance, default=Decimal(0), metavar="X",
        help="amounts whose difference is <= X count as matched (default: 0)",
    )
    parser.add_argument(
        "--format", choices=FORMATS, default="text", dest="fmt",
        help="output format (default: text)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        records_a = load_records(args.file_a)
        records_b = load_records(args.file_b)
    except InputError as exc:
        print(f"recon-cli: error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    result = reconcile(records_a, records_b, tolerance=args.tolerance)
    sys.stdout.write(format_result(result, args.fmt))
    return EXIT_DIFFERENCES if result.has_differences else EXIT_OK
