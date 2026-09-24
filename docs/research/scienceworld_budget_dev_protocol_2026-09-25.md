# ScienceWorld 开发集预算对照

## 问题与边界

本轮检查：固定 Agent 动作上限为 100，将环境步数预算从 100 改为 200，是否改变成功情况、完整计时过程与推理成本。

沿用已见开发题 v084、v085、v086，不使用测试题 v132。三道开发题的官方参考路径在此前审计中都能在 100 环境步内成功，所以本轮可能无法复现测试题的预算冲突。出现这种结果，就记录“本开发集未复现”，不为获得正结果继续挑题。本轮是 12 次开发集 Pilot，不是独立确认实验。

## 固定设置

- 3 道题 × 2 条件 × 2 档环境预算 × 1 次，共 12 episodes。
- 条件：`no_skill`、`semantic_body_retrieval`。后者沿用本地 MiniLM、v4d Skill 库与完整 Top-3 加载；不修改 Skill 内容。
- DeepSeek `deepseek-v4-flash`，temperature=0，thinking disabled，simplification=easy。沿用原系统提示与共享控制器。
- Agent 上限 100；环境上限分别 100、200。六个“任务×条件”配对中，三对先跑 100，另三对先跑 200。没有单独运行 Flat，因此本轮不能比较 Flat 与 Body。

启动脚本会核对官方 dev 划分、本地 ScienceWorld 版本和 MiniLM；不生成 Gold 路径。配对运行结束后检查任务文本、已加载 Skill 及其文本哈希一致。不一致则保留两次结果并停止，等待检查。初始观察的物品列表顺序仍可能变化，单次配对不能隔离模型与环境全部随机性。

## 参数和停止条件

`--max-steps` 保留原含义：限制 Agent 轨迹条目数，包括非法命令和控制器拦截。`--environment-max-steps` 新增环境步数上限；省略时仍等于 `--max-steps`。两者现在可以独立设置。

例如单次运行中的 `--max-steps 100 --environment-max-steps 200` 表示 Agent 最多尝试 100 次动作，环境最多允许 200 步预算。环境在一次命令后发现 `moves > limit` 才结束，长等待可能使最终计数超过上限。没有改成 `>=`，也没有修改环境时间推进规则。

新记录保留 `max_steps`、`termination_reason`，增加 `agent_max_steps`、`environment_max_steps`、`budget_protocol_version`、`agent_budget_exhausted`、`environment_budget_exhausted` 和初始观察文本哈希。两个 exhausted 标志表示计数触及／超过相应边界，不能单独当作失败判定；仍先看环境分数。

## 保存与解读

结果写入 `results/scienceworld_budget_dev.jsonl`，两档预算使用不同 run ID，避免汇总时混在一起：

- `scienceworld-budget-dev-env100-3x1`
- `scienceworld-budget-dev-env200-3x1`

先按预算分别报告六项核心指标：Task Success Rate、Input Tokens、Output Tokens、Total Tokens、End-to-End Latency、Cost per Successful Task。单次成功成本等于包括失败在内的总估计费用除以成功次数；无成功时为 null。保留当前 `latency_ms` 口径，环境初始化／关闭另计入 `runner_ms`。

随后逐题比较分数、动作数、环境步数、两种预算标志及是否完成两次计时。只有“100 档确实因环境预算终止，200 档完成了后续测量并成功”才是与预算解释一致的 Pilot 证据；仍需重复验证。若两档均成功，不能说加预算有效；若都因 Agent 动作上限结束，应将它与环境预算问题分开。

脚本累计已记录费用达到 0.25 美元后停止启动下一 episode。这个阈值不是账单硬上限：进行中的 episode 可能超过阈值，网络中断前未保存的请求费用也可能缺失。网络异常会停止运行；续跑只跳过已保存并通过校验的 episode，不恢复半途轨迹。

不将本轮结果追加到旧确认实验。修改共享代码后，旧确认脚本的冻结哈希检查会拒绝继续执行，这是预期保护。旧 JSONL 仍可汇总；需要复现旧代码时使用其对应 Git 版本，不更新旧 manifest 来绕过检查。

## 运行

默认预览不启动 Java 或模型；代码与计划已通过 `--prepare` 固定在 `results/scienceworld_budget_dev_manifest.json`。代码变化后不要删除已使用的 manifest 强行续跑。

```bash
cd "/Users/Check/Desktop/桌面ing/skill测试"
python3 scienceworld_budget_pilot.py
.venv/scienceworld/bin/python scienceworld_budget_pilot.py --check
.venv/scienceworld/bin/python scienceworld_budget_pilot.py --execute --resume
```

只有最后一行调用 DeepSeek。确保当前终端已有 `DEEPSEEK_API_KEY`，不要把密钥粘贴到聊天或提交仓库。中断后重用最后一行。查看进度不调用模型：

```bash
python3 scienceworld_budget_pilot.py --status
```

完成后分别汇总两档预算。本轮每档仅 3 道题、每条件只跑一次，不报告重复运行标准差。

```bash
python3 summarize_results.py results/scienceworld_budget_dev.jsonl --run-id scienceworld-budget-dev-env100-3x1 --deduplicate
python3 summarize_results.py results/scienceworld_budget_dev.jsonl --run-id scienceworld-budget-dev-env200-3x1 --deduplicate
```

离线测试，不调用 Java 或模型：

```bash
python3 -m unittest test_scienceworld_budgets test_scienceworld test_scienceworld_strong_retrieval test_scienceworld_budget_audit test_scienceworld_procedure_audit_v2
```
