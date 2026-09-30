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

## task-4：金额容差

- **先红**：写完 `tests/test_tolerance.py`（13 个用例）后运行，`12 failed, 1 passed`。失败原因均为 `TypeError: reconcile() got an unexpected keyword argument 'tolerance'`（唯一通过的是不带容差参数的 `test_default_tolerance_is_zero`）。
- **验收命令与结果**：`pytest -q` → `67 passed`（含前序任务，无回归）。
- **发现的问题**：
  1. **`Decimal` 减法受默认 28 位精度上下文影响，超长金额的 `difference` 被静默舍入**（例：`1000…0.00`（36 位整数）减 `0.01` 得到 `1.000000000000000000000000000E+35`，而不是 `99999999999999999999999999999999999.99`）。实现通过全部预设测试后，我复查时想到这一点，先写了一个用例，但**第一个版本的用例没有区分力**（差值位数很少，未触发舍入，直接通过）。用 REPL 确认舍入确实发生后，换成结果本身有 38 位的用例，红（`1 failed, 13 passed`）。修复：`_exact_difference()`，按两数的位数与指数算出所需精度，用独立 `Context` 做减法。这个场景对真实金额几乎不会出现，但对账工具不该在此处静默失真。
  2. 我在修改测试时曾留下一行无意义的 `... or True` 断言（会让该断言恒真），在提交前自查时删掉了。
  - 其余用例（边界等于容差、多一个最小单位、对称、浮点陷阱 `1.0 - 0.7`、负容差与 `NaN`/`Infinity` 容差）第一次实现即通过。

## task-5：结果格式化（json / text）

- **先红**：写完 `tests/test_report.py`（10 个用例）后运行，收集阶段 `ModuleNotFoundError`（模块不存在式的红）。
- **验收命令与结果**：`pytest -q` → `78 passed`（含前序任务，无回归）。
- **发现的问题**：
  1. **text 格式可被 id 里的换行"注入"假条目**。CSV 引号字段合法地允许换行，一个 id 为 `A1\n  fake_id: only in B` 的记录，在我第一版 text 输出里会变成两行，看起来像多出一条记录。实现通过全部预设测试后，我复查时想到；补测试先红（`1 failed, 10 passed`），再加 `_safe()`：不可打印字符转义为 `\n` 之类，可打印的非 ASCII（中文等）原样保留。JSON 输出由 `json.dumps` 负责转义，不受影响。
  - 其余用例（JSON 结构与键顺序、金额为字符串、`difference` 不使用科学计数法、确定性、中文 id 不转义、空结果）第一次实现即通过。`format(Decimal, "f")` 这一点是我在写实现时就特意处理的，测试只是确认。

## task-6：命令行入口与退出码

- **先红**：写完 `tests/test_cli.py`（13 个用例，用 `subprocess` 真实调用 `python -m recon_cli`）和 `examples/` 虚构示例数据后运行，`12 failed, 1 passed`。
- **验收命令与结果**：
  - `pytest -q` → `91 passed`（含前序任务，无回归）。
  - 手动：`pip install -e .` 后 `python -m recon_cli examples/ledger.csv examples/bank.csv --format json | python -m json.tool` 可解析；`recon-cli examples/ledger.csv examples/bank.csv` 退出码为 `1`，摘要 `matched=4 missing_in_a=1 missing_in_b=1 amount_mismatch=1`，与示例数据的设计一致。
  - `ruff check .` → `All checks passed!`。
- **发现的问题**：
  1. **我写的第一版测试有错**：示例数据的 `matched` 期望数我写成了 3（实际设计是 4），并且顺手写了一条 `... or True` 的恒真断言。运行前自己重读时发现，整个测试文件重写。（这一条没有被任何检查抓到，是重读发现的。）
  2. **唯一"通过"的那个红测试是假通过**：`12 failed, 1 passed` 里的那 1 个是 `test_works_from_any_cwd`。原因是 `__main__.py` 还不存在时，Python 自己以退出码 `1` 退出，恰好等于我们约定的"发现差异 = 1"，测试只断言了退出码，于是误过。我把它加强为同时断言 stdout 里的 JSON 内容，之后 13 个全红。教训：退出码 1 与 Python 自身的错误退出码冲突，只断言退出码不够。
  3. **文件不存在 / 路径是目录时，`OSError` 未被捕获**：实现 CLI 之后 `test_missing_file_is_input_error` 与 `test_directory_as_input_is_input_error` 失败（出栈并以退出码 1 退出，会被误读成"有差异"）。修复：`load_records` 里捕获 `OSError` 转成 `InputError`。
  4. **文档里的验收命令缺前置条件**：`docs/tasks.md` 里写的 `python -m recon_cli ...` 在包未安装时会报 `No module named recon_cli`（我实际跑时发现）。于是补全了 `pyproject.toml`（setuptools 构建、`recon-cli` 入口、ruff 配置，`pip install -e .` 可用），并在 `tasks.md` 中加上"先 `pip install -e .`，或临时设置 `PYTHONPATH=src`"。
  - 无效 `--tolerance`（`abc`、`-0.01`、`NaN`、`Infinity`、`1e2`）与无效 `--format` 的用例，交给 `argparse` 的 `type=`/`choices=` 处理，第一次实现即通过。
