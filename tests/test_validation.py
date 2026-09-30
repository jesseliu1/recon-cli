from decimal import Decimal

import pytest

from recon_cli.loader import InputError, load_records


def write(tmp_path, content: str, name="a.csv"):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def err(tmp_path, content) -> str:
    p = write(tmp_path, content)
    with pytest.raises(InputError) as e:
        load_records(p)
    return str(e.value)


def test_empty_amount(tmp_path):
    msg = err(tmp_path, "id,amount\nA1,\n")
    assert ":2:" in msg and "amount" in msg


def test_blank_amount(tmp_path):
    msg = err(tmp_path, "id,amount\nA1,   \n")
    assert ":2:" in msg


@pytest.mark.parametrize(
    "bad", ["abc", "1,000.00", "$5", "1e3", "NaN", "Infinity", "-Infinity", "1.2.3", "--1", "1_000"]
)
def test_invalid_amounts(tmp_path, bad):
    quoted = f'"{bad}"'
    msg = err(tmp_path, f"id,amount\nA1,{quoted}\n")
    assert ":2:" in msg and "invalid amount" in msg


@pytest.mark.parametrize(
    "good,expected",
    [("-3.50", "-3.50"), ("+0.5", "0.5"), (".5", "0.5"), ("7", "7"), ("0", "0"), ("-0.00", "0.00")],
)
def test_valid_amounts(tmp_path, good, expected):
    p = write(tmp_path, f"id,amount\nA1,{good}\n")
    assert load_records(p)[0].amount == Decimal(expected)


def test_empty_id(tmp_path):
    msg = err(tmp_path, "id,amount\n  ,5\n")
    assert ":2:" in msg and "id" in msg


def test_too_few_fields(tmp_path):
    msg = err(tmp_path, "id,amount\nA1\n")
    assert ":2:" in msg and "fields" in msg


def test_too_many_fields(tmp_path):
    msg = err(tmp_path, "id,amount\nA1,5,extra\n")
    assert ":2:" in msg and "fields" in msg


def test_duplicate_id_reports_both_lines(tmp_path):
    msg = err(tmp_path, "id,amount\nA1,1\nB2,2\nA1,3\n")
    assert ":4:" in msg and "duplicate" in msg and "line 2" in msg


def test_duplicate_id_after_trimming(tmp_path):
    msg = err(tmp_path, "id,amount\nA1,1\n A1 ,2\n")
    assert "duplicate" in msg


def test_ids_differing_by_case_are_not_duplicates(tmp_path):
    p = write(tmp_path, "id,amount\nA1,1\na1,2\n")
    assert len(load_records(p)) == 2


def test_blank_lines_skipped_and_line_numbers_stay_physical(tmp_path):
    p = write(tmp_path, "id,amount\n\nA1,1\n\n\nB2,2\n")
    recs = load_records(p)
    assert [(r.id, r.line) for r in recs] == [("A1", 3), ("B2", 6)]


def test_duplicate_header_columns(tmp_path):
    msg = err(tmp_path, "id,amount,id\nA1,1,A2\n")
    assert "duplicate column" in msg


def test_quoted_field_with_comma_and_newline(tmp_path):
    p = write(tmp_path, 'id,amount,memo\n"A,1",5,"line one\nline two"\nB2,6,ok\n')
    recs = load_records(p)
    assert [(r.id, r.line) for r in recs] == [("A,1", 2), ("B2", 4)]


@pytest.mark.parametrize("bad", ["１２", "٣", "1.５"])
def test_non_ascii_digits_rejected(tmp_path, bad):
    msg = err(tmp_path, f"id,amount\nA1,{bad}\n")
    assert "invalid amount" in msg
