# 任务拆解

`recon-cli` 是一个命令行 CSV 对账工具：比较两份 CSV（记为 A 与 B，例如 `ledger.csv` 与 `bank.csv`），
按 `id` 匹配，输出四类结果：`matched`、`missing_in_a`、`missing_in_b`、`amount_mismatch`。
支持 `--tolerance`（金额容差）与 `--format json|text`。

本文件在写任何代码之前完成。每个任务都包含：目标、输入输出、验收标准、明确不做什么。
验收标准都写成"可以用一条命令或一个测试验证"的形式，评审 AI 产出时以这些标准为准，而不是以"看起来对"为准。

## 需求中不明确之处：我的假设

需求原文没有规定下面这些点。为了让任务可验收，先在这里定死，后续测试都以此为准。
如果假设有误，改这里，再改测试，最后才改代码。

| 编号 | 假设 |
|---|---|
| A1 | 每个 CSV 必须有表头，必须包含 `id` 与 `amount` 两列。列顺序无关，表头名区分大小写，首尾空白会被去掉。其他列忽略。 |
| A2 | `id` 去首尾空白后按字符串精确匹配，区分大小写。去空白后为空的 `id` 视为错误。 |
| A3 | `amount` 用 `decimal.Decimal` 解析，不使用 float。只接受形如 `12`、`-3.50`、`+0.5`、`.5` 的十进制写法。不接受千分位、货币符号、科学计数法、`NaN`、`Infinity`。 |
| A4 | 金额为空、金额非法、`id` 为空、行字段数与表头不一致，都是输入错误。报错信息带文件路径与行号，不静默当成 0，也不静默跳过。 |
| A5 | 同一文件内出现重复 `id`，视为输入错误并退出，不做静默合并或"取最后一条"。对账工具悄悄吞数据比报错更危险。 |
| A6 | 容差比较为 `abs(a - b) <= tolerance`，边界值算匹配。默认容差为 0（即精确相等，`1.0` 与 `1.00` 相等）。容差必须是不小于 0 的十进制数。 |
| A7 | 落入容差内但不完全相等的记录归入 `matched`，并在条目中保留两边原始金额。超出容差的归入 `amount_mismatch`，条目带 `difference = amount_b - amount_a`。 |
| A8 | 文件编码只支持 UTF-8，允许带 BOM。其他编码（含非法 UTF-8 字节）报输入错误，不做编码猜测。 |
| A9 | 输出按 `id` 的字符串升序排序，保证同一输入永远得到同一输出。 |
| A10 | 退出码：`0` 表示没有任何差异（只有 `matched`）；`1` 表示存在差异（任一其他三类非空）；`2` 表示输入或用法错误。错误信息写到 stderr，结果写到 stdout。 |
| A11 | 完全空行被跳过；空文件（没有表头）是输入错误；只有表头没有数据行是合法的，结果各类均为空。 |
| A12 | 金额原样以字符串形式输出（保留输入的写法），只有 `difference` 是计算值。 |

## 任务列表

共 7 个任务，按顺序推进，每个任务一个 commit，commit message 格式为 `task-N: 简述`。
（文档本身作为 `task-0` 提交。）

### 任务 1：读取 CSV，得到 `id -> 金额` 记录

- **目标**：实现 `load_records(path)`：读取一个 CSV，返回记录列表，每条含 `id`、`amount`（`Decimal`）、`amount_text`（原始字符串）、`line`（行号）。
- **输入**：CSV 文件路径。文件含 `id`、`amount` 两列，可能有额外列，列顺序任意，可能带 UTF-8 BOM，字段首尾可能有空格。
- **输出**：记录列表（保持文件顺序）。缺少必需列、空文件、非法 UTF-8 抛出 `InputError`，信息含文件路径。
- **验收标准**：
  - `pytest tests/test_loader.py -q` 全部通过。
  - 测试覆盖：正常读取；列顺序相反；额外列被忽略；BOM；字段首尾空白；缺少 `id` 列；缺少 `amount` 列；空文件；只有表头；非法 UTF-8。
- **不做**：不校验每行的值是否合法（任务 2）；不做去重（任务 2）；不做比较；不写 CLI。

### 任务 2：行级校验与重复 id

- **目标**：在 `load_records` 内加入逐行校验，遇到问题给出带行号的 `InputError`。
- **输入**：可能含脏数据的 CSV。
- **输出**：合法文件行为与任务 1 相同；非法文件抛 `InputError`，信息形如 `<path>:<line>: <原因>`。
- **验收标准**：
  - `pytest tests/test_validation.py -q` 全部通过。
  - 测试覆盖：金额为空；金额为空白；金额非法（`abc`、`1,000.00`、`$5`、`1e3`、`NaN`、`Infinity`）；负数、`+` 号、`.5`、无小数点整数为合法；`id` 为空；字段数少于或多于表头；同一文件重复 `id`（信息需同时含两处行号）；完全空行被跳过；表头重复列名。
- **不做**：不尝试修复或猜测脏数据；不提供"跳过坏行继续"的模式；不做跨文件比较。

### 任务 3：核心比较（精确相等）

- **目标**：实现 `reconcile(records_a, records_b, tolerance=Decimal(0))`，先完成容差为 0 的情形，得出四类结果。
- **输入**：两个已校验的记录列表。
- **输出**：`ReconResult`，含 `matched`、`missing_in_a`、`missing_in_b`、`amount_mismatch` 四个列表，均按 `id` 升序。
  - `missing_in_a`：id 只出现在 B。`missing_in_b`：id 只出现在 A。
  - `matched` 条目含 `id`、`amount_a`、`amount_b`。`amount_mismatch` 条目另含 `difference`。
- **验收标准**：
  - `pytest tests/test_compare.py -q` 全部通过。
  - 测试覆盖：全部匹配；只在 A；只在 B；金额不同；`1.0` 与 `1.00` 视为相等；负数金额；两边都为空列表；`difference` 的符号与精度（`Decimal` 精确，不出现 `0.30000000000000004` 之类）。
- **不做**：不处理容差（任务 4）；不做输出格式（任务 5）；不读文件。

### 任务 4：金额容差

- **目标**：`reconcile` 支持 `tolerance`，语义见假设 A6、A7。
- **输入**：`tolerance: Decimal`，必须 `>= 0`。
- **输出**：容差内的金额差异归 `matched`，超出归 `amount_mismatch`。负容差抛 `ValueError`。
- **验收标准**：
  - `pytest tests/test_tolerance.py -q` 全部通过。
  - 测试覆盖：差值恰好等于容差（算匹配）；差值比容差多最小一位小数（算不匹配）；差值为负数方向（B 小于 A）对称；容差为 0；容差大于所有差值；负容差报错；用 `Decimal` 而不是 float 的边界（如 `0.1 + 0.2` 类场景）。
- **不做**：不支持百分比容差；不支持按类别设置不同容差；不解析命令行（任务 6）。

### 任务 5：结果格式化（json / text）

- **目标**：实现 `format_result(result, fmt)`，`fmt` 为 `json` 或 `text`。
- **输入**：`ReconResult` 与格式名。
- **输出**：
  - `json`：一个 JSON 对象，键为 `summary`（四类各自的数量）与四类列表；金额以字符串输出；键顺序固定；`ensure_ascii=False`；以换行结尾。
  - `text`：人类可读，先一行汇总，再按类别分段列出，每类为空时仍打印类别标题及 `(none)`。
  - 未知格式抛 `ValueError`。
- **验收标准**：
  - `pytest tests/test_report.py -q` 全部通过。
  - 测试覆盖：JSON 可被 `json.loads` 解析且结构符合上述约定；金额为字符串；同一输入两次输出字节相同；text 含四个类别标题；空结果；含非 ASCII 的 id（如中文 id）在 JSON 中不被转义；未知格式。
- **不做**：不做颜色、表格库、CSV 输出；不做分页；不写文件（只返回字符串）。

### 任务 6：命令行入口与退出码

- **目标**：`python -m recon_cli A.csv B.csv [--tolerance X] [--format json|text]`，并提供 `examples/` 中的虚构示例数据。
- **输入**：两个位置参数（文件路径），`--tolerance`（默认 `0`），`--format`（默认 `text`）。
- **输出**：结果写 stdout；错误写 stderr；退出码遵循假设 A10。
- **验收标准**：
  - `pytest tests/test_cli.py -q` 全部通过（测试以 `subprocess` 真实调用 `python -m recon_cli`）。
  - 手动验收（先在虚拟环境里 `pip install -e .`，或临时设置 `PYTHONPATH=src`）：`python -m recon_cli examples/ledger.csv examples/bank.csv --format json` 的退出码为 `1`，输出可被 `python -m json.tool` 解析。
  - 测试覆盖：退出码 0/1/2 三种；文件不存在；非法 `--tolerance`（`abc`、负数）；非法 `--format`；输入文件有脏数据时退出码 2 且 stderr 含行号；stdout 与 stderr 分离；示例数据的期望输出。
- **不做**：不做交互式界面；不读 stdin；不做配置文件；不做彩色输出；不做日志系统。

### 任务 7：大文件与性能冒烟

- **目标**：确认读取是逐行流式的，不把整个文件按文本一次性读入；对 20 万行量级的文件在合理时间内完成。
- **输入**：测试内动态生成的大 CSV（写到 pytest 的 `tmp_path`，不提交到仓库）。
- **输出**：与小文件相同的结果结构。
- **验收标准**：
  - `pytest tests/test_large.py -q` 通过。
  - 测试覆盖：20 万行两个文件对账，结果数量与生成时的预期一致；用 `tracemalloc` 断言峰值内存低于一个宽松上限；耗时上限设为宽松值（避免在慢机器上误报），只用于发现数量级退化。
  - `docs/verification.md` 中的独立核对方法（awk / sqlite）在同样数据上给出相同计数。
- **不做**：不做多进程、不做外部排序、不做数据库落盘。全量 `id -> 金额` 仍放内存字典，超出内存的文件不在范围内（已记录为已知限制）。

## 收尾（不算任务）

README、`docs/verification.md`、LICENSE、pyproject 的最终版本、`ruff` 检查与 README 的 Status 一节，在任务 7 之后一次性完成。
