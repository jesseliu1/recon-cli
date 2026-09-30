# 不依赖 AI 的独立验收方法

目的：不信任本仓库的测试（它们和实现出自同一个作者），用**别的工具**对**同一份数据**算一遍，看结果是否一致。
下面每一种方法都不使用 `recon_cli` 的任何代码。

## 方法 1：一条命令做三方核对（awk + sqlite3 + recon-cli）

```bash
pip install -e .                                   # 或 export PYTHONPATH=src
scripts/cross_check.sh                             # 示例数据，容差 0
scripts/cross_check.sh examples/ledger.csv examples/bank.csv 10   # 容差 0.10（单位：分）
scripts/cross_check.sh --large                     # 用 awk 生成 20 万行数据再核对
```

脚本分别用 `recon-cli`、`awk`、`sqlite3` 计算四类的数量，三者不一致时退出码为 1。
`awk` 与 `sqlite3` 都把金额换算成"整数分"再比较，所以不会有浮点问题，也与本工具的 `Decimal` 实现是不同的路径。

我实际运行的结果（本机，2026-09）：

| 数据 | recon-cli | awk | sqlite3 |
|---|---|---|---|
| 示例，容差 0 | matched=4 missing_in_a=1 missing_in_b=1 amount_mismatch=1 | 同左 | 同左 |
| 示例，容差 0.10 | matched=5 missing_in_a=1 missing_in_b=1 amount_mismatch=0 | 同左 | 同左 |
| `--large`（20 万行） | matched=197010 missing_in_a=500 missing_in_b=1000 amount_mismatch=1990 | 同左 | 同左 |

## 方法 2：用纸笔从数据设计反推期望值

`--large` 的数据是按规则生成的，期望值可以直接算出，不必运行任何程序：

- A 有 `ID-0000000 … ID-0199999`，共 200000 行。B 缺少前 1000 个，另外多出 500 个新 id。
  所以 `missing_in_b = 1000`，`missing_in_a = 500`。
- 两边都有的是 `i ∈ [1000, 200000)`，共 199000 个。其中 `i % 100 == 0` 的金额在 B 里加了 0.05：
  从 1000 到 199900 每隔 100 一个，共 `(199900 - 1000) / 100 + 1 = 1990` 个，所以 `amount_mismatch = 1990`。
- `matched = 199000 - 1990 = 197010`。

示例数据（`examples/`）同理，可以肉眼核对：

| id | ledger | bank | 期望 |
|---|---|---|---|
| TX-1001 | 120.00 | 120.00 | matched |
| TX-1002 | 45.50 | 45.50 | matched |
| TX-1003 | 900.00 | 899.90 | amount_mismatch，差 -0.10；容差 ≥ 0.10 时变为 matched |
| TX-1004 | 15.99 | 15.99 | matched |
| TX-1005 | 300.00 | 无 | missing_in_b |
| TX-1006 | -50.00 | -50.00 | matched（负数） |
| TX-1007 | 无 | 72.25 | missing_in_a |

## 方法 3：手工 sqlite 查询

```bash
sqlite3 :memory: <<'SQL'
.mode csv
.import examples/ledger.csv a
.import examples/bank.csv b
.mode column
.headers on
SELECT a.id, a.amount AS a_amt, b.amount AS b_amt
FROM a JOIN b USING(id)
WHERE CAST(ROUND(CAST(a.amount AS REAL)*100) AS INTEGER)
   != CAST(ROUND(CAST(b.amount AS REAL)*100) AS INTEGER);
SELECT id AS only_in_a FROM a WHERE id NOT IN (SELECT id FROM b);
SELECT id AS only_in_b FROM b WHERE id NOT IN (SELECT id FROM a);
SQL
```

期望：一行差异（TX-1003），`only_in_a` 为 TX-1005，`only_in_b` 为 TX-1007。

## 方法 4：不变量检查（对任意输入都成立）

对任意合法输入，用 `--format json` 的输出验证下面的等式，不需要知道"正确答案"：

- `matched + amount_mismatch + missing_in_b == A 的行数`（A 内没有重复 id）。
- `matched + amount_mismatch + missing_in_a == B 的行数`。
- 交换 A、B 后，`missing_in_a` 与 `missing_in_b` 互换，`matched` 与 `amount_mismatch` 的数量不变，`difference` 变号。
- 容差从 0 逐步变大，`matched` 单调不减，`amount_mismatch` 单调不增，两者之和不变。

```bash
python -m recon_cli examples/ledger.csv examples/bank.csv --format json |
  python -c 'import json,sys; s=json.load(sys.stdin)["summary"]; print(s["matched"]+s["amount_mismatch"]+s["missing_in_b"], "== rows in A:", 6)'
```

## 这些方法的局限（不夸大）

- awk 与 sqlite3 方法按"整数分"比较，只适用于至多两位小数、无带逗号的引号字段的数据；这足以核对示例与大数据，但不是对所有边界情况的证明。
- 金额超长（如 30+ 位数字）、非 ASCII 数字、BOM、重复 id、非法金额等边界，这里没有独立核对，只有 `tests/` 中的测试覆盖。
- 三种方法只核对四类的**数量**（方法 2、3 也核对了具体 id），没有逐字节比对 JSON 输出。
