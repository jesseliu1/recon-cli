from decimal import Decimal

import pytest

from recon_cli.loader import InputError, load_records


def write(tmp_path, content: str | bytes, name="a.csv"):
    p = tmp_path / name
    if isinstance(content, str):
        content = content.encode("utf-8")
    p.write_bytes(content)
    return p


def test_basic_read(tmp_path):
    p = write(tmp_path, "id,amount\nA1,10.50\nA2,3\n")
    recs = load_records(p)
    assert [r.id for r in recs] == ["A1", "A2"]
    assert [r.amount for r in recs] == [Decimal("10.50"), Decimal("3")]
    assert [r.amount_text for r in recs] == ["10.50", "3"]
    assert [r.line for r in recs] == [2, 3]


def test_column_order_reversed(tmp_path):
    p = write(tmp_path, "amount,id\n10.50,A1\n")
    recs = load_records(p)
    assert recs[0].id == "A1" and recs[0].amount == Decimal("10.50")


def test_extra_columns_ignored(tmp_path):
    p = write(tmp_path, "date,id,memo,amount\n2024-01-01,A1,hello,5\n")
    recs = load_records(p)
    assert len(recs) == 1 and recs[0].id == "A1"


def test_bom_is_stripped(tmp_path):
    p = write(tmp_path, b"\xef\xbb\xbfid,amount\nA1,1\n")
    recs = load_records(p)
    assert recs[0].id == "A1"


def test_whitespace_trimmed(tmp_path):
    p = write(tmp_path, " id , amount \n  A1 , 10.5 \n")
    recs = load_records(p)
    assert recs[0].id == "A1"
    assert recs[0].amount_text == "10.5"


def test_missing_id_column(tmp_path):
    p = write(tmp_path, "amount\n1\n")
    with pytest.raises(InputError) as e:
        load_records(p)
    assert "id" in str(e.value)
    assert str(p) in str(e.value)


def test_missing_amount_column(tmp_path):
    p = write(tmp_path, "id\nA1\n")
    with pytest.raises(InputError) as e:
        load_records(p)
    assert "amount" in str(e.value)


def test_empty_file(tmp_path):
    p = write(tmp_path, b"")
    with pytest.raises(InputError):
        load_records(p)


def test_header_only(tmp_path):
    p = write(tmp_path, "id,amount\n")
    assert load_records(p) == []


def test_invalid_utf8(tmp_path):
    p = write(tmp_path, b"id,amount\n\xff\xfe,1\n")
    with pytest.raises(InputError) as e:
        load_records(p)
    assert "UTF-8" in str(e.value)


def test_header_names_are_case_sensitive(tmp_path):
    p = write(tmp_path, "ID,Amount\nA1,1\n")
    with pytest.raises(InputError):
        load_records(p)
