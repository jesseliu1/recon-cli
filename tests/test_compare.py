from decimal import Decimal

from recon_cli.compare import reconcile
from recon_cli.loader import Record


def rec(id_, amount, line=2):
    return Record(id=id_, amount=Decimal(amount), amount_text=amount, line=line)


def ids(items):
    return [i.id for i in items]


def test_all_matched():
    r = reconcile([rec("A", "1"), rec("B", "2")], [rec("B", "2"), rec("A", "1")])
    assert ids(r.matched) == ["A", "B"]
    assert not (r.missing_in_a or r.missing_in_b or r.amount_mismatch)


def test_only_in_a_is_missing_in_b():
    r = reconcile([rec("A", "1"), rec("B", "2")], [rec("A", "1")])
    assert ids(r.missing_in_b) == ["B"]
    assert r.missing_in_b[0].amount_a == "2"
    assert r.missing_in_b[0].amount_b is None
    assert r.missing_in_a == []


def test_only_in_b_is_missing_in_a():
    r = reconcile([rec("A", "1")], [rec("A", "1"), rec("C", "9")])
    assert ids(r.missing_in_a) == ["C"]
    assert r.missing_in_a[0].amount_b == "9"
    assert r.missing_in_a[0].amount_a is None


def test_amount_mismatch_with_difference():
    r = reconcile([rec("A", "10.00")], [rec("A", "10.25")])
    assert ids(r.amount_mismatch) == ["A"]
    item = r.amount_mismatch[0]
    assert (item.amount_a, item.amount_b) == ("10.00", "10.25")
    assert item.difference == Decimal("0.25")
    assert r.matched == []


def test_difference_sign_is_b_minus_a():
    r = reconcile([rec("A", "10")], [rec("A", "7")])
    assert r.amount_mismatch[0].difference == Decimal("-3")


def test_numerically_equal_different_spelling_matches():
    r = reconcile([rec("A", "1.0"), rec("B", "5")], [rec("A", "1.00"), rec("B", "5.000")])
    assert ids(r.matched) == ["A", "B"]
    assert r.matched[0].amount_a == "1.0" and r.matched[0].amount_b == "1.00"


def test_negative_amounts():
    r = reconcile([rec("A", "-5.5"), rec("B", "-1")], [rec("A", "-5.5"), rec("B", "1")])
    assert ids(r.matched) == ["A"]
    assert r.amount_mismatch[0].difference == Decimal("2")


def test_both_empty():
    r = reconcile([], [])
    assert (r.matched, r.missing_in_a, r.missing_in_b, r.amount_mismatch) == ([], [], [], [])


def test_difference_is_exact_decimal():
    r = reconcile([rec("A", "0.1")], [rec("A", "0.3")])
    assert r.amount_mismatch[0].difference == Decimal("0.2")


def test_results_sorted_by_id_string_order():
    a = [rec("b", "1"), rec("B", "1"), rec("a2", "1"), rec("a10", "1")]
    r = reconcile(a, list(a))
    assert ids(r.matched) == ["B", "a10", "a2", "b"]


def test_ids_are_case_sensitive():
    r = reconcile([rec("a1", "1")], [rec("A1", "1")])
    assert ids(r.missing_in_b) == ["a1"] and ids(r.missing_in_a) == ["A1"]


def test_duplicate_ids_passed_directly_are_rejected():
    import pytest

    with pytest.raises(ValueError, match="duplicate"):
        reconcile([rec("A", "1"), rec("A", "2")], [rec("A", "1")])
    with pytest.raises(ValueError, match="duplicate"):
        reconcile([rec("A", "1")], [rec("A", "1"), rec("A", "2")])
