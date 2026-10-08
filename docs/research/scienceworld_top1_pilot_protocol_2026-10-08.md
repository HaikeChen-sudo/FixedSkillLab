# ScienceWorld Top-1 针对性开发 Pilot

运行标识：`scienceworld-top1-mechanism-dev-4x3`。计划 36 个 episode，当前仅完成代码与本地预检，尚未调用 DeepSeek。

## 问题与边界

上一轮离线检查发现，两条“寻找非生物”查询中，Flat 第一名是寻找生物 Skill，Body 第一名是寻找非生物 Skill。本轮检查这种排序差异是否影响 Agent 完成任务，以及正确 Skill 相对 No Skill 是否有净收益。

选择两个分歧实例 `find-non-living-thing:v150/v151`，并使用 `find-living-thing:v150/v151` 作为第一名相同的对照。四题均来自官方 dev 划分。此选择受已见离线结果影响，是针对性开发诊断，不是独立测试集确认，也不能代表 ScienceWorld 整体。

| 实验组 | 选择规则 | 加载内容 |
| --- | --- | --- |
| no_skill | 不检索 | 无 Skill |
| semantic_flat_top1 | MiniLM 检索 Name＋Description，取第一名 | 一个完整 Skill |
| semantic_body_top1 | MiniLM 检索完整 Skill，取第一名 | 一个完整 Skill |

每题每组三次，4 × 3 × 3 = 36 个 episode。沿用同一个冻结的 v3 Skill 库、本地 MiniLM 和 DeepSeek 模型名称 `deepseek-v4-flash`；temperature=0，thinking disabled，simplification=easy。Agent 调用轨迹上限 100，环境 move 上限 100。模型别名相同不保证供应商后台版本永远不变，因此不把跨日期差异解释为方法效果。

同一道题的三组在每次重复中轮换位置，保证每组各占首、中、末位一次；任务顺序使用固定种子 20261008。没有新控制器，也没有修改 Skill 内容。两种索引继续使用原有 Top-3 排序器，随后仅加载第一名；元数据同时记录 `top_k=1` 与 `ranker_returned_top_k=3`。Gold 不参与排序。

## 实现与保护

在线改动仅在 `scienceworld_agent.py` 增加两个新条件，旧 Top-3 条件及默认实验组保持不变。专用入口 `scienceworld_top1_pilot.py` 保存 36 条运行计划与代码、来源数据、环境版本哈希。默认只预览；只有 `--execute` 会调用 DeepSeek。

预检会重新核验官方 dev 归属、题目描述、实际 Top-1 结果及完整 Skill 提示哈希。运行结束时先保存 episode，再检查协议；不因失败或异常结果而删记录。续跑拒绝重复 episode、不同预算、不同模型、不同查询或提示文本混入。

本轮使用独立的 `results/scienceworld_top1_pilot.jsonl`。一次只开一个运行进程。按 Ctrl+C 中断后，重新执行同一条 `--execute --resume` 命令会跳过已保存的完整 episode；未完成的 episode 会重跑。中断或通信失败的部分请求可能已产生费用，但不在完成记录中，不能把结果文件中的费用当作完整账单。

沿用代码内冻结的历史计价参数，已完成记录估算合计达到 0.25 美元后，不再启动下一个 episode。这不是当前价格核验或账户硬限额；运行中的 episode、未落盘请求及网络重试可能使实际费用超过阈值。需要硬上限时，应使用服务商账户侧限额。

旧实验清单若包含修改前的 Agent 哈希，可能拒绝继续执行，这是版本隔离保护。不要重写旧清单来绕过检查；旧结果仍可使用原汇总脚本读取。

## 指标

六项均保留：Task Success Rate、Input Tokens、Output Tokens、Total Tokens、End-to-End Latency、Cost per Successful Task。成功只由环境 score≥100 判定；每成功任务成本等于所有完成 episode 的估算成本之和除以成功数，无成功时为 null。

`latency_ms` 沿用旧计时边界，从环境对象创建后到 episode 结束，包含 reset、检索、模型与工具执行；现有汇总脚本输出这个值。另存 `runner_ms`，包含环境对象创建与关闭，用于严格的完整 episode 端到端墙钟时间；两者不能混称。一次性批量预检不计入各 episode 时延。

还保存 score、llm_calls、tool_calls、环境 moves、实际加载 Skill、排名、提示哈希和完整轨迹。分析时先按生物／非生物两个家族分别看配对结果，再报告总表；重复运行不增加独立任务数量。Body 仅胜过 Flat、却未胜过 No Skill 时，应优先解释为避免错误 Skill 干扰，而不是证明 Skill 本身有净收益。

## 运行

清单已准备好，不要修改或重新生成以覆盖当前协议。以下命令在项目目录执行。

```sh
python3 scienceworld_top1_pilot.py --status
.venv/scienceworld/bin/python scienceworld_top1_pilot.py --execute --resume
```

若提示缺少 API Key，在当前 zsh 终端隐藏输入，不将 Key 粘贴进聊天或代码：

```sh
read -rs 'DEEPSEEK_API_KEY?输入 DeepSeek API Key（不显示）：'
export DEEPSEEK_API_KEY
```

运行完成后汇总：

```sh
python3 summarize_results.py results/scienceworld_top1_pilot.jsonl --run-id scienceworld-top1-mechanism-dev-4x3 --deduplicate --repeat-stats
```

每组应有 12 条完成记录，三组共 36 条。失败任务也属于完成记录，不应通过重跑失败题提高成功率。

本地复查命令，不调用 API：

```sh
.venv/scienceworld/bin/python scienceworld_top1_pilot.py --check
python3 -m unittest test_scienceworld_top1_pilot test_scienceworld_strong_retrieval test_scienceworld_budgets test_scienceworld_top1_audit test_scienceworld_top1_dev_probe -v
```

开发验证：28 项测试中 27 项通过，1 项默认跳过；另行执行的真实本地预检已通过四道题的 8 次检索与提示文本检查，API 调用为 0。
