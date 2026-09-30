"""Render a ReconResult as JSON or text."""

from __future__ import annotations

import json

from recon_cli.compare import Item, ReconResult

CATEGORIES = ("matched", "missing_in_a", "missing_in_b", "amount_mismatch")
FORMATS = ("json", "text")


def format_result(result: ReconResult, fmt: str) -> str:
    if fmt == "json":
        return _to_json(result)
    if fmt == "text":
        return _to_text(result)
    raise ValueError(f"unknown format {fmt!r}; expected one of {', '.join(FORMATS)}")


def _item_dict(item: Item) -> dict[str, str]:
    d = {"id": item.id}
    if item.amount_a is not None:
        d["amount_a"] = item.amount_a
    if item.amount_b is not None:
        d["amount_b"] = item.amount_b
    if item.difference is not None:
        d["difference"] = format(item.difference, "f")
    return d


def _to_json(result: ReconResult) -> str:
    doc: dict[str, object] = {
        "summary": {name: len(getattr(result, name)) for name in CATEGORIES}
    }
    for name in CATEGORIES:
        doc[name] = [_item_dict(i) for i in getattr(result, name)]
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def _safe(text: str) -> str:
    """Keep one entry on one line even if an id contains control characters."""
    return "".join(
        ch if ch.isprintable() else ch.encode("unicode_escape").decode("ascii")
        for ch in text
    )


def _describe(name: str, item: Item) -> str:
    item_id = _safe(item.id)
    if name == "matched":
        return f"{item_id}: {item.amount_a} vs {item.amount_b}"
    if name == "missing_in_a":
        return f"{item_id}: only in B (amount {item.amount_b})"
    if name == "missing_in_b":
        return f"{item_id}: only in A (amount {item.amount_a})"
    diff = format(item.difference, "f")
    return f"{item_id}: {item.amount_a} vs {item.amount_b} (B - A = {diff})"


def _to_text(result: ReconResult) -> str:
    counts = " ".join(f"{n}={len(getattr(result, n))}" for n in CATEGORIES)
    lines = [f"Summary: {counts}"]
    for name in CATEGORIES:
        items = getattr(result, name)
        lines.append("")
        lines.append(f"{name} ({len(items)})")
        if not items:
            lines.append("  (none)")
        lines.extend(f"  {_describe(name, i)}" for i in items)
    return "\n".join(lines) + "\n"
