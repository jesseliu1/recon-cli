import json
from decimal import Decimal

import pytest

from recon_cli.compare import Item, ReconResult
from recon_cli.report import format_result


def sample() -> ReconResult:
    return ReconResult(
        matched=[Item("A1", "10.00", "10.00")],
        missing_in_a=[Item("C3", amount_b="7")],
        missing_in_b=[Item("B2", amount_a="5.5")],
        amount_mismatch=[Item("D4", "1.00", "1.30", Decimal("0.30"))],
    )


def test_json_structure():
    data = json.loads(format_result(sample(), "json"))
    assert list(data) == ["summary", "matched", "missing_in_a", "missing_in_b", "amount_mismatch"]
    assert data["summary"] == {
        "matched": 1, "missing_in_a": 1, "missing_in_b": 1, "amount_mismatch": 1
    }
    assert data["matched"] == [{"id": "A1", "amount_a": "10.00", "amount_b": "10.00"}]
    assert data["missing_in_a"] == [{"id": "C3", "amount_b": "7"}]
    assert data["missing_in_b"] == [{"id": "B2", "amount_a": "5.5"}]
    assert data["amount_mismatch"] == [
        {"id": "D4", "amount_a": "1.00", "amount_b": "1.30", "difference": "0.30"}
    ]


def test_json_amounts_are_strings():
    data = json.loads(format_result(sample(), "json"))
    for key in ("matched", "missing_in_a", "missing_in_b", "amount_mismatch"):
        for item in data[key]:
            assert all(isinstance(v, str) for v in item.values())


def test_json_difference_never_uses_exponent_notation():
    r = ReconResult(amount_mismatch=[Item("X", "0", "1E+3", Decimal("1E+3"))])
    data = json.loads(format_result(r, "json"))
    assert data["amount_mismatch"][0]["difference"] == "1000"


def test_json_is_deterministic_and_newline_terminated():
    out1 = format_result(sample(), "json")
    out2 = format_result(sample(), "json")
    assert out1 == out2 and out1.endswith("\n") and not out1.endswith("\n\n")


def test_json_does_not_escape_non_ascii():
    r = ReconResult(matched=[Item("订单-001", "1", "1")])
    out = format_result(r, "json")
    assert "订单-001" in out and "\\u" not in out


def test_text_has_all_category_headings_and_summary():
    out = format_result(sample(), "text")
    assert out.splitlines()[0] == (
        "Summary: matched=1 missing_in_a=1 missing_in_b=1 amount_mismatch=1"
    )
    for heading in ("matched (1)", "missing_in_a (1)", "missing_in_b (1)", "amount_mismatch (1)"):
        assert heading in out
    assert "D4" in out and "0.30" in out
    assert out.endswith("\n")


def test_text_empty_result_still_lists_every_category():
    out = format_result(ReconResult(), "text")
    for name in ("matched", "missing_in_a", "missing_in_b", "amount_mismatch"):
        assert f"{name} (0)" in out
    assert out.count("(none)") == 4


def test_empty_result_json():
    data = json.loads(format_result(ReconResult(), "json"))
    assert data["summary"] == {
        "matched": 0, "missing_in_a": 0, "missing_in_b": 0, "amount_mismatch": 0
    }


def test_text_is_deterministic():
    assert format_result(sample(), "text") == format_result(sample(), "text")


def test_unknown_format():
    with pytest.raises(ValueError, match="format"):
        format_result(sample(), "xml")


def test_text_escapes_control_characters_in_ids():
    r = ReconResult(missing_in_b=[Item("A1\n  fake_id: only in B", amount_a="1")])
    out = format_result(r, "text")
    assert "A1\\n" in out
    # one heading line + exactly one entry line for the category
    section = out.split("missing_in_b (1)\n", 1)[1].split("\n\n", 1)[0]
    assert len(section.splitlines()) == 1
