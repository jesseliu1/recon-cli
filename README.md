# recon-cli

命令行 CSV 对账工具（Python 3.11+，只用标准库；开发时用 pytest 与 ruff）。
比较两份 CSV（如 `ledger.csv` 与 `bank.csv`），按 `id` 匹配，输出四类结果：

| 类别 | 含义 |
|---|---|
| `matched` | 两边都有，金额相等（或差值在容差内） |
| `missing_in_a` | id 只出现在第二个文件（B） |
| `missing_in_b` | id 只出现在第一个文件（A） |
| `amount_mismatch` | 两边都有，但金额差值超出容差 |

这个仓库同时是一份"如何拆任务、定验收标准、评审 AI 产出"的过程样本：代码由 AI 助手（Claude）在人类给定的任务与验收标准下逐任务完成，
过程文档与代码同等重要，见下文"如何拆任务与验收"。所有示例数据均为自行合成的虚构数据。

## 安装与用法

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # 运行工具本身不需要第三方依赖，[dev] 只装 pytest 和 ruff
```

```bash
recon-cli examples/ledger.csv examples/bank.csv                       # 文本输出（默认）
recon-cli examples/ledger.csv examples/bank.csv --format json         # JSON 输出
recon-cli examples/ledger.csv examples/bank.csv --tolerance 0.10      # 差值 <= 0.10 视为匹配（含边界）
python -m recon_cli examples/ledger.csv examples/bank.csv             # 等价写法
```

输入要求：UTF-8（允许 BOM），必须有表头，必须含 `id` 与 `amount` 两列，列顺序无关，其他列忽略。
金额只接受 `12`、`-3.50`、`+0.5`、`.5` 这类十进制写法。完整的规则与假设见 [docs/tasks.md](docs/tasks.md)。

示例输出（文本，节选）：

```
Summary: matched=4 missing_in_a=1 missing_in_b=1 amount_mismatch=1

missing_in_a (1)
  TX-1007: only in B (amount 72.25)

missing_in_b (1)
  TX-1005: only in A (amount 300.00)

amount_mismatch (1)
  TX-1003: 900.00 vs 899.90 (B - A = -0.10)
```

### 退出码

| 退出码 | 含义 |
|---|---|
| 0 | 没有差异（只有 `matched`） |
| 1 | 存在差异（其余三类任一非空） |
| 2 | 输入或用法错误（文件不存在、脏数据、重复 id、非法参数），错误信息在 stderr，带文件名与行号 |

## 运行测试

```bash
pytest -q          # 93 个测试，其中大文件用例约 10 秒
ruff check .
scripts/cross_check.sh          # 用 awk 与 sqlite3 独立核对，见 docs/verification.md
```

## 如何拆任务与验收

先写文档、后写代码；每个任务先写测试并确认失败，再实现，一个任务一个 commit（`task-N: 简述`）。

- [docs/tasks.md](docs/tasks.md)：需求中不明确之处的**假设（A1–A12）**，以及 7 个任务。每个任务写明目标、输入输出、可用命令或测试验证的验收标准、明确不做什么。
- [docs/edge-cases.md](docs/edge-cases.md)：29 条边界情况（重复 id、金额为空、编码、负数、容差边界、超大文件、列顺序不同等），每条映射到覆盖它的任务；并列出"已知不覆盖"的范围。
- [docs/review-log.md](docs/review-log.md)：每个任务的验收命令与结果，以及实现过程中**真实**发现的问题（模型写错了什么、被哪个测试或检查发现、怎么修）。没有问题就写"无"。
  这份记录如实包含了不好看的部分，例如：一个"先红"的测试其实在模块不存在时也误过；一次我在没看清输出时就写了"ruff 通过"，事后更正；以及任务 7 没有红阶段。
- [docs/verification.md](docs/verification.md)：不依赖 AI 的独立验收方法（awk、sqlite3、纸笔推算、不变量检查），并说明这些方法的局限。

提交历史即任务顺序：

```bash
git log --oneline
```

### 关于这些记录的来源

代码和 review-log 都由 AI 助手在人类指定的任务与验收标准下产出，review-log 中"模型写错了什么"是该助手对自己产出的复查记录，
因此它只能反映助手自己发现的问题；`docs/verification.md` 的独立核对正是为了不完全依赖这种自查。

## Status

在 Python 3.11.16、pytest 9.1.1、ruff 0.16.9 下运行：

| 检查 | 结果 |
|---|---|
| `pytest -q` | `93 passed in 10.01s` |
| `ruff check .` | `All checks passed!` |
| `scripts/cross_check.sh`（示例数据，容差 0 与 0.10） | recon-cli、awk、sqlite3 三方一致 |
| `scripts/cross_check.sh --large`（20 万行） | 三方一致：`matched=197010 missing_in_a=500 missing_in_b=1000 amount_mismatch=1990` |

已知限制：

- 全量 `id -> 金额` 放内存，内存占用与行数成正比（20 万行两个文件约 160–190 MB 峰值）；超出内存的文件不支持。
- 只支持 UTF-8；重复 id 直接报错，不支持一对多对账。
- 大文件测试的时间与内存阈值有意放宽，只能发现数量级退化。

## 许可证

MIT，见 [LICENSE](LICENSE)。
