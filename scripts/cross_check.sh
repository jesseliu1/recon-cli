#!/usr/bin/env bash
# Independent cross-check of recon-cli using only awk and sqlite3.
#
#   scripts/cross_check.sh                # examples/ledger.csv vs examples/bank.csv
#   scripts/cross_check.sh A.csv B.csv 5  # your files, tolerance in cents (integer)
#   scripts/cross_check.sh --large        # generate 200k-row files with awk, then compare
#
# Amounts are compared as integer cents, so this only supports data with at most
# two decimal places and no quoted fields containing commas.
set -euo pipefail

if [ "${1:-}" = "--large" ]; then
  work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
  A="$work/a.csv"; B="$work/b.csv"; TOL_CENTS=0
  N=200000
  awk -v n="$N" 'BEGIN{print "id,amount,memo"; for(i=0;i<n;i++) printf "ID-%07d,%d.%02d,row %d\n", i, i%977, i%100, i}' > "$A"
  awk -v n="$N" 'BEGIN{print "amount,id"
    for(i=1000;i<n;i++){c=(i%977)*100+(i%100); if(i%100==0)c+=5; printf "%d.%02d,ID-%07d\n", int(c/100), c%100, i}
    for(i=n;i<n+500;i++) printf "1.00,ID-%07d\n", i}' > "$B"
else
  A="${1:-examples/ledger.csv}"; B="${2:-examples/bank.csv}"; TOL_CENTS="${3:-0}"
fi
TOL="$(awk -v c="$TOL_CENTS" 'BEGIN{printf "%d.%02d", int(c/100), c%100}')"

echo "== recon-cli (tolerance $TOL) =="
tool="$(python -m recon_cli "$A" "$B" --tolerance "$TOL" --format json | python -c \
  'import json,sys; s=json.load(sys.stdin)["summary"]; print(*(f"{k}={s[k]}" for k in ("matched","missing_in_a","missing_in_b","amount_mismatch")))' || true)"
echo "$tool"

echo "== awk =="
awk_out="$(awk -F, -v tol="$TOL_CENTS" '
  function cents(s,   p, w, f) {                 # "12.5" -> 1250, "-3.50" -> -350
    sub(/^\+/, "", s); sign = (s ~ /^-/) ? -1 : 1; sub(/^-/, "", s)
    p = index(s, "."); w = p ? substr(s, 1, p-1) : s; f = p ? substr(s, p+1) : ""
    f = substr(f "00", 1, 2); return sign * (w * 100 + f)
  }
  FNR == 1 { for (i = 1; i <= NF; i++) { h = $i; gsub(/^ +| +$/, "", h); col[h] = i }; ic = col["id"]; ac = col["amount"]; next }
  NR == FNR { if ($0 != "") { id = $ic; gsub(/^ +| +$/, "", id); a[id] = cents($ac) }; next }
  $0 != "" { id = $ic; gsub(/^ +| +$/, "", id); seen[id] = 1
    if (!(id in a)) miss_a++
    else { d = cents($ac) - a[id]; if (d < 0) d = -d; if (d <= tol) m++; else mm++ } }
  END { for (id in a) if (!(id in seen)) miss_b++
        printf "matched=%d missing_in_a=%d missing_in_b=%d amount_mismatch=%d\n", m, miss_a, miss_b, mm }
' "$A" "$B")"
echo "$awk_out"

echo "== sqlite3 =="
sql_out="$(sqlite3 :memory: <<SQL
.mode csv
.import '$A' a
.import '$B' b
CREATE TABLE ca (id TEXT PRIMARY KEY, c INTEGER) WITHOUT ROWID;
CREATE TABLE cb (id TEXT PRIMARY KEY, c INTEGER) WITHOUT ROWID;
INSERT INTO ca SELECT trim(id), CAST(ROUND(CAST(amount AS REAL)*100) AS INTEGER) FROM a;
INSERT INTO cb SELECT trim(id), CAST(ROUND(CAST(amount AS REAL)*100) AS INTEGER) FROM b;
.mode list
.separator " "
SELECT
 'matched=' || (SELECT count(*) FROM ca JOIN cb USING(id) WHERE abs(ca.c-cb.c) <= $TOL_CENTS),
 'missing_in_a=' || (SELECT count(*) FROM cb WHERE id NOT IN (SELECT id FROM ca)),
 'missing_in_b=' || (SELECT count(*) FROM ca WHERE id NOT IN (SELECT id FROM cb)),
 'amount_mismatch=' || (SELECT count(*) FROM ca JOIN cb USING(id) WHERE abs(ca.c-cb.c) > $TOL_CENTS);
SQL
)"
echo "$sql_out"

if [ "$tool" = "$awk_out" ] && [ "$tool" = "$sql_out" ]; then
  echo "RESULT: all three agree"
else
  echo "RESULT: MISMATCH between recon-cli, awk and sqlite3" >&2; exit 1
fi
