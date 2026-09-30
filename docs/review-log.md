# 评审记录（review-log）

每完成一个任务追加一条。规则：

- 只记录真实发生的事：哪个测试或检查失败、失败信息是什么、怎么修的。
- "测试先红"指先运行测试并确认它因为功能缺失而失败，再写实现。红的输出摘要如实摘录。
- 没有发现问题就写"无"，不编造。
- 代码与本记录都由 AI 助手（Claude）在人类给定的任务与验收标准下产出；"发现的问题"里的"模型"即该助手。

---

## task-0：任务拆解与边界情况（仅文档）

- **验收命令与结果**：无可执行验收。人工核对：`docs/tasks.md` 含 7 个任务，每个任务都有目标、输入输出、验收标准、不做什么；`docs/edge-cases.md` 含 28 条边界情况，每条都映射到具体任务。
- **发现的问题**：无。

## task-1：读取 CSV

- **先红**：写完 `tests/test_loader.py`（11 个用例）后运行 `pytest tests/test_loader.py -q`，收集阶段报错 `ModuleNotFoundError: No module named 'recon_cli.loader'`。这是"模块还不存在"式的红，能证明测试确实在调用尚未实现的代码，但对逻辑本身的区分力有限。
- **验收命令与结果**：`pytest tests/test_loader.py -q` → `11 passed`。
- **发现的问题**：无。
  - 说明：按任务边界，这一步的 `Decimal(amount_text)` 是未加保护的，非法金额会抛出 `decimal.InvalidOperation` 而不是 `InputError`，这是有意留给任务 2 的，不算本任务的缺陷。

## task-2：行级校验与重复 id

- **先红**：写完 `tests/test_validation.py`（27 个用例）后运行，`19 failed, 8 passed`。失败类型：
  - 非法金额 `abc`、`1,000.00`、`$5`、`1.2.3`、`--1`、空金额：抛出裸的 `decimal.InvalidOperation`，而不是 `InputError`。
  - `1e3`、`NaN`、`Infinity`、`-Infinity`、`1_000`：`Decimal()` 直接接受，没有任何报错（`DID NOT RAISE`）。
  - 空行：`IndexError`；字段数过少：`IndexError`；字段数过多、空 id、重复 id、重复列名：都没有报错。
- **验收命令与结果**：`pytest -q` → 实现后全部通过（含任务 1 的 11 个用例，无回归）。
- **发现的问题**：
  1. **`Decimal` 会接受 `NaN`/`Infinity`/`1e3`/`1_000`**（预期内，已列在 `edge-cases.md` #3）。由上面的红测试发现。修复：用显式正则 `[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)` 做 `fullmatch`，通过后才交给 `Decimal`。
  2. **我第一版正则用了 `\d`，它在 Python 3 里匹配 Unicode 数字**（全角 `１２`、阿拉伯-印度数字 `٣` 会被当成合法金额，然后被 `Decimal` 静默接受）。这个问题**不是被预先写好的测试发现的**，是我实现完后自己复查时想到的，随后补了 `test_non_ascii_digits_rejected`，确认先红（3 failed）再修：把 `\d` 改为 `[0-9]`。教训：边界情况清单漏了"非 ASCII 数字"这一条，补充见 `edge-cases.md` #29。

## task-3：核心比较（精确相等）

- **先红**：写完 `tests/test_compare.py`（11 个用例中的前 10 个）后运行，收集阶段 `ModuleNotFoundError`（模块不存在式的红）。
- **验收命令与结果**：`pytest -q` → `53 passed`（含任务 1、2 的全部用例，无回归）。
- **发现的问题**：
  1. **`reconcile` 对重复 id 静默"后者覆盖前者"**。第一版用 `{r.id: r for r in records}` 建索引，实现后自己复查时发现：`load_records` 虽然拒绝重复 id，但 `reconcile` 是公开函数，直接传入含重复 id 的列表时会悄悄丢一条记录，违背假设 A5（对账工具不应静默吞数据）。这不是预设测试发现的，是复查发现的。补了 `test_duplicate_ids_passed_directly_are_rejected`，先红（`1 failed, 11 passed`），再加 `_index()` 检查并抛 `ValueError`。
  - 其余用例（`1.0` 与 `1.00` 相等、`difference` 符号、`Decimal` 精确差值、排序、大小写敏感）第一次实现即通过，没有发现问题。
