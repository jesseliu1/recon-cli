import time
import tracemalloc
from decimal import Decimal

from recon_cli.compare import reconcile
from recon_cli.loader import load_records

N = 200_000
MISSING_IN_B = 1_000      # ids 0..999 are absent from B
EXTRA_IN_B = 500          # ids N..N+499 exist only in B
MISMATCH_EVERY = 100      # every 100th id (that is present in both) differs by 0.05

# Deliberately loose limits: they exist to catch order-of-magnitude
# regressions (e.g. quadratic behaviour), not to benchmark.
MAX_SECONDS = 30
MAX_PEAK_BYTES = 400 * 1024 * 1024


def build_files(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    with (
        a.open("w", encoding="utf-8", newline="") as fa,
        b.open("w", encoding="utf-8", newline="") as fb,
    ):
        fa.write("id,amount,memo\n")
        fb.write("amount,id\n")
        for i in range(N):
            amount = f"{i % 977}.{i % 100:02d}"
            fa.write(f"ID-{i:07d},{amount},row {i}\n")
            if i < MISSING_IN_B:
                continue
            if i % MISMATCH_EVERY == 0:
                b_amount = str(Decimal(amount) + Decimal("0.05"))
            else:
                b_amount = amount
            fb.write(f"{b_amount},ID-{i:07d}\n")
        for i in range(N, N + EXTRA_IN_B):
            fb.write(f"1.00,ID-{i:07d}\n")
    return a, b


def expected_mismatches():
    return sum(1 for i in range(MISSING_IN_B, N) if i % MISMATCH_EVERY == 0)


def test_200k_rows_counts_time_and_memory(tmp_path):
    a, b = build_files(tmp_path)
    mismatches = expected_mismatches()

    tracemalloc.start()
    started = time.perf_counter()
    result = reconcile(load_records(a), load_records(b))
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert len(result.missing_in_b) == MISSING_IN_B
    assert len(result.missing_in_a) == EXTRA_IN_B
    assert len(result.amount_mismatch) == mismatches
    assert len(result.matched) == N - MISSING_IN_B - mismatches
    assert result.amount_mismatch[0].difference == Decimal("0.05")
    assert elapsed < MAX_SECONDS, f"took {elapsed:.1f}s"
    assert peak < MAX_PEAK_BYTES, f"peak {peak / 1e6:.0f} MB"


def test_tolerance_on_large_input_turns_all_mismatches_into_matches(tmp_path):
    a, b = build_files(tmp_path)
    result = reconcile(load_records(a), load_records(b), tolerance=Decimal("0.05"))
    assert result.amount_mismatch == []
    assert len(result.matched) == N - MISSING_IN_B
