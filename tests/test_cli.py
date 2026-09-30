import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "examples" / "ledger.csv"
BANK = ROOT / "examples" / "bank.csv"


def run(*args, cwd=None):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "recon_cli", *map(str, args)],
        capture_output=True, text=True, env=env, cwd=cwd,
    )


def write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_example_json_output_and_exit_code_1():
    p = run(LEDGER, BANK, "--format", "json")
    assert p.returncode == 1 and p.stderr == ""
    data = json.loads(p.stdout)
    assert data["summary"] == {
        "matched": 4, "missing_in_a": 1, "missing_in_b": 1, "amount_mismatch": 1
    }
    assert [i["id"] for i in data["matched"]] == ["TX-1001", "TX-1002", "TX-1004", "TX-1006"]
    assert data["missing_in_a"] == [{"id": "TX-1007", "amount_b": "72.25"}]
    assert data["missing_in_b"] == [{"id": "TX-1005", "amount_a": "300.00"}]
    assert data["amount_mismatch"] == [
        {"id": "TX-1003", "amount_a": "900.00", "amount_b": "899.90", "difference": "-0.10"}
    ]


def test_default_format_is_text():
    p = run(LEDGER, BANK)
    assert p.returncode == 1
    assert p.stdout.startswith("Summary: matched=4 ")


def test_tolerance_turns_mismatch_into_match_at_boundary():
    p = run(LEDGER, BANK, "--tolerance", "0.10", "--format", "json")
    data = json.loads(p.stdout)
    assert data["summary"]["amount_mismatch"] == 0 and data["summary"]["matched"] == 5
    p = run(LEDGER, BANK, "--tolerance=0.09", "--format", "json")
    assert json.loads(p.stdout)["summary"]["amount_mismatch"] == 1


def test_exit_code_0_when_no_differences(tmp_path):
    a = write(tmp_path, "a.csv", "id,amount\nX,1\nY,2.5\n")
    b = write(tmp_path, "b.csv", "id,amount\nY,2.50\nX,1.00\n")
    p = run(a, b)
    assert p.returncode == 0 and p.stderr == ""


def test_exit_code_0_when_both_have_only_headers(tmp_path):
    a = write(tmp_path, "a.csv", "id,amount\n")
    b = write(tmp_path, "b.csv", "amount,id\n")
    assert run(a, b).returncode == 0


def test_missing_file_is_input_error(tmp_path):
    p = run(tmp_path / "nope.csv", BANK)
    assert p.returncode == 2 and p.stdout == ""
    assert "nope.csv" in p.stderr and "Traceback" not in p.stderr


def test_directory_as_input_is_input_error(tmp_path):
    p = run(tmp_path, BANK)
    assert p.returncode == 2 and "Traceback" not in p.stderr


def test_bad_row_reports_file_and_line_on_stderr(tmp_path):
    a = write(tmp_path, "a.csv", "id,amount\nX,1\nY,oops\n")
    p = run(a, BANK)
    assert p.returncode == 2 and p.stdout == ""
    assert "a.csv:3" in p.stderr and "Traceback" not in p.stderr


def test_duplicate_id_is_exit_2(tmp_path):
    a = write(tmp_path, "a.csv", "id,amount\nX,1\nX,2\n")
    p = run(a, BANK)
    assert p.returncode == 2 and "duplicate" in p.stderr


def test_invalid_tolerance_values():
    for bad in ("abc", "-0.01", "NaN", "Infinity", "1e2"):
        p = run(LEDGER, BANK, f"--tolerance={bad}")
        assert p.returncode == 2, bad
        assert "tolerance" in p.stderr and p.stdout == ""


def test_invalid_format():
    p = run(LEDGER, BANK, "--format", "xml")
    assert p.returncode == 2 and "format" in p.stderr


def test_missing_arguments():
    p = run(LEDGER)
    assert p.returncode == 2 and p.stdout == ""


def test_works_from_any_cwd(tmp_path):
    p = run(LEDGER, BANK, "--format", "json", cwd=tmp_path)
    # Exit code 1 alone proves nothing: Python itself exits 1 when the module
    # cannot be run. Check that real output was produced.
    assert p.returncode == 1 and json.loads(p.stdout)["summary"]["matched"] == 4
