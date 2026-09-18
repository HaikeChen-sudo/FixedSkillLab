# 固定 Skill 在三个环境中的收益边界

2026-09-18｜现有实验汇总，不含新模型调用

## 摘要

同样是给 DeepSeek Agent 加载人工固定 Skill，三个环境给出了不同结果。Mini Lab 的 10 道多步骤 Pilot 题在五个条件下全部成功，无法测出成功率收益。ALFWorld v5 的 No Skill 已成功 88/90 次，Body-aware Retrieval 成功 85/90 次，平均 Total Tokens 增加 66.8%。ScienceWorld v11b 的 No Skill 成功 42/54 次，Body-aware 成功 48/54 次，平均 Total Tokens 减少 66.6%。ALFWorld v8 的定向 Oracle 确认也未复现效率收益。

这些结果支持一项有限判断：**固定 Skill 的收益依赖当前任务、Agent 协议与 Skill 内容，不能把 ScienceWorld 的正结果推广成普遍规律。** ScienceWorld 的收益与困难任务上的长轨迹减少同时出现；三套环境的设计不同，现有数据不能证明“轨迹长”本身是收益原因。

## 1. 选取哪些实验

| 环境与批次 | 题目与重复 | 客观成功条件 | 在本文中的作用 |
|---|---|---|---|
| Mini Lab `v4-pilot-10x1` | 10 道选定的 `hard-*` 链式题，每条件 1 次 | 程序检查提交值或输出文件 | 管线验证；不是正式确认 |
| ALFWorld `alfworld-v5-test-30x3` | `valid_unseen` 六类目标各 5 题，每条件 3 次 | 环境 `won` 为真 | 六类任务的主要负结果 |
| ScienceWorld `scienceworld-v11b-confirm-18x3` | 官方 test split 六类任务各 3 个 variation，每条件 3 次 | 环境分数 ≥100 | 固定 Skill 检索的主要正结果 |
| ALFWorld `alfworld-v8-confirm-20x3` | `valid_seen` 加热与双物体目标共 20 题，每条件 3 次 | 环境 `won` 为真 | 改写 Oracle Skill 后的定向确认 |

所有批次请求 `deepseek-v4-flash`、temperature 0，成功判定均来自程序或环境。Mini Lab 有 16 个工具和 30 个固定 Skill；ALFWorld 使用文字动作工具及 30 个 Skill；ScienceWorld 使用其文字动作工具及 6 个 Skill。三套任务、动作空间、提示、Skill 库和步数预算均不相同。本文只计算**各批次内**的差值，不合并跨环境 episode，也不比较不同环境的绝对 Token 或美元成本高低。

Mini Lab 选用 `v4-pilot-10x1`，因为其 50 个 episode 键唯一。此前的 `v3-answer-types` 原始文件有 300 行，但仅有 150 个唯一的题目、重复编号、条件组合；[阶段报告](../../MINILAB_PHASE1_REPORT.md)已披露同一 run ID 被使用两次。v3 不进入本文的数值主比较。仓库未保存 `v4-small-30x3` 的正式运行轨迹，故不能把 Mini Lab 写成完成了 30 题三次重复的实验。

## 2. 六项核心指标

表 1 的 Token 和延迟均为每个 episode 的平均值。每次成功成本 = 该条件全部 episode 的 `cost_usd` 之和 ÷ 成功 episode 数。保留整数 Token 只是显示取整；未取整值参与比较。Mini Lab 为单次 Pilot，不报告标准差或显著性。

| 批次 / 条件 | 成功率 | Input Tokens | Output Tokens | Total Tokens | 延迟，秒 | 每次成功成本，USD |
|---|---:|---:|---:|---:|---:|---:|
| Mini Lab v4 / No Skill | 10/10，100% | 7,677 | 415 | 8,092 | 7.55 | 0.000232 |
| Mini Lab v4 / Body-aware | 10/10，100% | 8,760 | 415 | 9,175 | 8.71 | 0.000242 |
| ALFWorld v5 / No Skill | 88/90，97.78% | 27,547 | 1,065 | 28,612 | 16.67 | 0.000599 |
| ALFWorld v5 / Body-aware | 85/90，94.44% | 46,404 | 1,314 | 47,718 | 20.66 | 0.000830 |
| ScienceWorld v11b / No Skill | 42/54，77.78% | 876,950 | 3,755 | 880,705 | 88.18 | 0.007201 |
| ScienceWorld v11b / Body-aware | 48/54，88.89% | 292,543 | 1,919 | 294,462 | 48.01 | 0.002851 |

| 同批次 Body-aware − No Skill | 成功率差，百分点 | Total Tokens 变化 | 延迟变化 | 每次成功成本变化 |
|---|---:|---:|---:|---:|
| Mini Lab v4 Pilot | 0 | +13.4% | +15.4% | +4.1% |
| ALFWorld v5 | -3.33 | +66.8% | +24.0% | +38.6% |
| ScienceWorld v11b | +11.11 | -66.6% | -45.6% | -60.4% |

ALFWorld v5 的 Body-aware 成功率配对差为 -3.33 个百分点，任务级 Bootstrap 95% CI 为 [-8.89, 0]；区间包含 0。No Skill 的成功率已达 97.78%，同时比 Body-aware 更省 Token、时间和成本。改用 BM25 正文检索后，成功率回到 88/90，与 No Skill 相同，但平均 Total Tokens 为 39,912，仍高于 No Skill 的 28,612。把全部 Skill 都给模型，成功率为 89/90，平均 Total Tokens 升至 95,278；这 1 次净增成功不足以支持普遍效率优势。

ScienceWorld v11b 的 Body-aware 成功率配对差为 +11.11 个百分点，按 18 道 task-variation 重新抽样的 Bootstrap 95% CI 为 [1.85, 22.22]。平均 Total Tokens 差为 -586,243，95% CI 为 [-1,261,769, -128,184]。改进仅见于 4/18 道题，另 14 道持平；11/18 道题的 Token 更低。平均 Token 的大幅减少受几道极长 No Skill 失败轨迹影响。Body-aware 相对 Flat 的成功率差尚未排除 0，因此该批次不能单独证明“索引正文”优于“只索引名称与描述”。[主线证据审计](scienceworld_mainline_evidence_audit.md)列出任务复用、协议冻结与哈希检查。

## 3. ALFWorld v8 的定向验证

v8 不使用 Body-aware Router，而是直接加载已知对应任务的 Oracle v7 Skill；它只覆盖加热与双物体放置两类目标，不能代替六类任务的 v5 结果。

| 条件 | 成功率 | Input Tokens | Output Tokens | Total Tokens | 延迟，秒 | 每次成功成本，USD |
|---|---:|---:|---:|---:|---:|---:|
| No Skill | 60/60，100% | 45,035 | 1,135 | 46,170 | 24.60 | 0.000738 |
| Oracle v7 | 60/60，100% | 60,337 | 1,191 | 61,528 | 28.67 | 0.000848 |

Oracle v7 没有成功率空间可提升，平均 Total Tokens 比 No Skill 高 33.3%。任务级 Bootstrap 的 Token、延迟和每 episode 成本差区间均跨过 0；不应把观察到的均值差写成确定的成本惩罚。该批次能支持的判断是：定向改写的 Skill 没有复现先前开发集中的效率收益。

## 4. 结果为何不同：可观察事实与未验证解释

Mini Lab v4 的五个条件均为 10/10。ALFWorld v5 的 No Skill 为 88/90，v8 为 60/60。成功率接近上限时，新增 Skill 很难表现出正向成功率差，但仍可能增加上下文。Mini Lab v4 的 Body-aware 比 No Skill 多用 13.4% Total Tokens；ALFWorld v5 多用 66.8%。这解释了**评价空间的限制**，没有解释 Skill 本身为何在 ALFWorld 无效。

ScienceWorld v11b 的 No Skill 仅为 42/54，平均调用 74.9 次动作工具；Body-aware 成功 48/54，平均调用 42.3 次。26/27 个失败 episode 用尽环境动作预算。成功率净增集中在 `boil`、`freeze` 和 `find-living-thing`；三类较容易的任务在多数条件中接近满分。较短的执行轨迹与较低的累计 Input Tokens 一致，因为 Agent 每轮都会带上对话历史。现有数据仍无法在“Skill 步骤有用”“Router 换了 Skill 组合”“环境任务本身不同”等解释之间单独归因。v11b 的 `boil` 题即使没有检出人工 Gold Skill，Body-aware 仍全部完成。

不能把三套环境当成一个随机分组实验。它们使用不同题目、Skill 内容与数量、动作接口、检索查询和步数预算；Mini Lab 的计时从环境重置后开始，ALFWorld 与 ScienceWorld 的计时覆盖各自 episode 初始化之后的不同步骤。因此，跨环境差异是**异质性线索**，不是“长程任务必然受益”的因果检验。

## 5. 下一项可检验的问题

下一轮如要检验“长程或易循环任务更可能受益”，应先选择新的任务类型或新环境，冻结任务清单与 Skill 内容，并用**运行前可测**的任务属性定义难度，例如由环境专家路径得到的最短动作数。不要用同一轮 No Skill 的失败结果先挑题、再声称 Skill 对困难题有效。预设主比较为 Body-aware 对 No Skill，同时保留 Flat Retrieval，报告全部六项指标、逐题配对差与失败轨迹。若新测试仍无优势，就把“受益只在现有 ScienceWorld 套件中出现”写作边界结论。

## 数据来源与核查

- Mini Lab：[阶段报告](../../MINILAB_PHASE1_REPORT.md)；本地 `results/results.jsonl` 中 `v4-pilot-10x1` 的 50 条原始记录。该 JSONL 未纳入 Git，Mini Lab 数值需借助本地文件复核。
- ALFWorld v5：[冻结轨迹](../../results/formal_v5/alfworld-v5-test-30x3.jsonl)、[条件汇总](../../results/formal_v5/condition_summary.csv)、[配对结果](../../results/formal_v5/paired_comparisons.csv)。450 条记录与 manifest 的 SHA-256 一致，无重复键。
- ALFWorld v8：[冻结轨迹](../../results/formal_v8/alfworld-v8-confirm-20x3.jsonl)、[条件汇总](../../results/formal_v8/condition_summary.csv)、[配对结果](../../results/formal_v8/analysis_summary.json)。180 条记录与 manifest 的 SHA-256 一致，无重复键。
- ScienceWorld v11b：[冻结轨迹](../../results/formal_scienceworld_v11/scienceworld-v11b-confirm-18x3.jsonl)、[条件汇总](../../results/formal_scienceworld_v11/condition_summary.csv)、[配对结果](../../results/formal_scienceworld_v11/paired_statistics.csv)。162 条记录与 manifest 的 SHA-256 一致，无重复键。

本报告独立重算各条件成功数、Input/Output/Total Tokens、延迟与每次成功成本；所有冻结轨迹逐条满足 `Total Tokens = Input + Output`。统计区间沿用各实验的原分析文件，未跨环境重新估计共同效应。
