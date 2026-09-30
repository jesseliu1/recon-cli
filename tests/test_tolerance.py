from decimal import Decimal

import pytest

from recon_cli.compare import reconcile
from recon_cli.loader import Record


def rec(id_, amount):
    return Record(id=id_, amount=Decimal(amount), amount_text=amount, line=2)


def run(a, b, tol):
    return reconcile([rec("X", a)], [rec("X", b)], tolerance=Decimal(tol))


def test_difference_exactly_equal_to_tolerance_matches():
    r = run("10.00", "10.05", "0.05")
    assert [i.id for i in r.matched] == ["X"] and not r.amount_mismatch


def test_difference_one_smallest_unit_over_tolerance_mismatches():
    r = run("10.00", "10.06", "0.05")
    assert [i.id for i in r.amount_mismatch] == ["X"] and not r.matched
    assert r.amount_mismatch[0].difference == Decimal("0.06")


def test_symmetric_when_b_is_smaller():
    assert run("10.05", "10.00", "0.05").matched
    assert run("10.06", "10.00", "0.05").amount_mismatch


def test_zero_tolerance_is_exact():
    assert run("1", "1.00", "0").matched
    assert run("1", "1.01", "0").amount_mismatch


def test_default_tolerance_is_zero():
    r = reconcile([rec("X", "1")], [rec("X", "1.01")])
    assert r.amount_mismatch


def test_tolerance_larger_than_any_difference():
    assert run("1", "999", "1000").matched


def test_within_tolerance_match_keeps_original_amounts():
    item = run("10.00", "10.03", "0.05").matched[0]
    assert (item.amount_a, item.amount_b) == ("10.00", "10.03")


def test_decimal_arithmetic_not_float():
    # In binary floating point 1.0 - 0.7 == 0.30000000000000004 > 0.3.
    assert run("0.7", "1.0", "0.3").matched


def test_negative_amounts_and_tolerance():
    assert run("-10.00", "-10.05", "0.05").matched
    assert run("-10.00", "-10.06", "0.05").amount_mismatch


def test_negative_tolerance_rejected():
    with pytest.raises(ValueError, match="tolerance"):
        run("1", "1", "-0.01")


@pytest.mark.parametrize("bad", ["NaN", "Infinity"])
def test_non_finite_tolerance_rejected(bad):
    with pytest.raises(ValueError, match="tolerance"):
        run("1", "1", bad)


def test_missing_records_unaffected_by_tolerance():
    r = reconcile([rec("A", "1")], [rec("B", "1")], tolerance=Decimal("100"))
    assert [i.id for i in r.missing_in_b] == ["A"]
    assert [i.id for i in r.missing_in_a] == ["B"]


def test_difference_with_many_digits_is_not_rounded():
    # Default Decimal context keeps 28 significant digits; the true
    # difference here has 38, so an unguarded subtraction is rounded.
    huge = "1" + "0" * 35 + ".00"
    r = run("0.01", huge, "0")
    assert r.amount_mismatch[0].difference == Decimal("99999999999999999999999999999999999.99")
