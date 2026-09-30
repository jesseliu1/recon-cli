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
