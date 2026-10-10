# FixedSkillLab：项目说明与结果复核

更新日期：2026-10-10

FixedSkillLab 是一个固定 Skill 加载与检索的 LLM Agent 实验平台。项目从确定性 Mini Lab 开始，扩展到 ALFWorld 和 ScienceWorld，比较不同加载条件下的任务完成情况与执行成本。

本阶段实验已经结束。仓库保留代码、实验协议、已保存记录和离线分析入口，供检查与复用。当前成果是实证技术报告，不提出新检索算法，不声称固定 Skill 普遍有效或无效。

## 研究问题

- 固定指导在什么实验设置下改善任务完成，代价是多少？
- 元数据检索与正文检索的排名差异，是否改变了模型实际收到的指导？
- 加入更强的检索基线后，原有差距是否保留？
- 从局部执行轨迹提出的动作解释，能否通过后续固定对照？

Skill 在运行前固定，运行中不自动学习或演化。Agent 负责模型与工具之间的执行循环；成功由程序或环境判断，不让模型给自己的回答打分。

Flat 与 Body 描述的是检索索引差别。选中后，两组通常都加载完整 Skill，不能把 Flat 理解成模型只看到名称与描述。Oracle 使用人工指定的 Skill，但不保证该指导一定正确或有效。

## 材料范围

[中文技术报告](research/fixedskilllab_paper_draft_2026-10-09.md)主要讨论以下七批记录。它们不是一次统一设计的大样本实验，也不涵盖仓库的全部历史运行。

| 批次 | 实例×条件×重复 | 完成记录 |
| --- | --- | ---: |
| ALFWorld v5 | 30×5×3 | 450 |
| ALFWorld v8 | 20×3×3 | 180 |
| ScienceWorld v11b | 18×3×3 | 162 |
| ScienceWorld v13b | 6×3×3 | 54 |
| 语义 Top-3 | 6×3×3 | 54 |
| 语义 Top-1 dev | 4×3×3 | 36 |
| 固定内容 dev | 4×4×3 | 48 |

合计 984 条完成记录，不是 984 个独立任务。部分批次复用了实例；三次重复也不增加独立任务数。Mini Lab 主要用于工具协议和评分管线检查，不进入这七批的主要效果比较。

## 主要观察与解释边界

| 观察 | 可以支持的判断 | 不能推出的结论 |
| --- | --- | --- |
| ScienceWorld v11b 中 No Skill 成功 42/54，Body 成功 48/54；ALFWorld 部分批次没有同方向净收益。 | 固定指导在部分所测设置中有局部收益。 | Skill 普遍有效，或收益差异由环境类型单独造成。 |
| 保存的 v3 库查询中，BM25 和 MiniLM 的 Flat／Body Hit@3 均为 48/48。 | 强基线限制了旧哈希检索结果的解释。 | 小库结果能够外推到大规模 Skill 库。 |
| 语义 Top-3 的 18 个配对中，12 对加载相同 Skill 提示；同提示配对贡献的 Token 节省超过全批净节省。 | 汇总成本差异不能直接归为正文检索选出了更好的内容。 | 差异全部由模型随机性造成，或正文检索没有效果。 |
| 固定内容四组均成功 12/12，但联合减少调用与拾取命令的实例数为 0/4，要求至少 3/4。 | 该动作解释没有通过预定开发判据。 | 所有任务中的直接移动策略均无效。 |

报告保留正结果、负结果和慢运行。没有删除不利实例，也没有在判据未通过后追加有利题目改变结论。结果的集中度、任务选择和实际加载内容应与条件均值一起阅读。

## 六项主指标

| 指标 | 口径 |
| --- | --- |
| Task Success Rate | 成功完成数／已保存的完成记录数；同时报告分子与分母。 |
| Input Tokens | 每个 episode 内所有模型调用的累计输入，再对条件求均值。 |
| Output Tokens | 每个 episode 内的累计输出，单独列示。 |
| Total Tokens | Input 与 Output 之和。 |
| End-to-End Latency | 有记录时使用 `runner_ms`；旧 `latency_ms` 单独列为原计时。 |
| Cost per Successful Task | 包括失败记录在内的累计估算费用／成功数；零成功时未定义。 |

Input Tokens 包含多轮重复发送的历史，不等于 Skill 长度。Token 数不等于 GPU FLOPs、显存占用或能耗。部分旧批次缺少完整端到端时间，不补造数值。费用使用历史记录中的价格与缓存计量估算，未与提供商账单核对；未保存为完整 episode 的中断请求费用不在其中。

## 从哪里开始复核

所有命令均在仓库根目录执行。以下流程只分析已保存的数据，不调用付费模型，不启动 ALFWorld／ScienceWorld，也不下载模型；需要 Python 3.9 或更新版本。

```sh
python3 -m unittest test_scienceworld_content_analysis test_scienceworld_top1_analysis -v
python3 scienceworld_content_analysis.py
python3 scienceworld_top1_analysis.py --output results/scienceworld_top1_public_recheck.json
```

测试中有一项会故意尝试覆盖不同分析结果，因此会显示一次错误文本；最终测试汇总为 `OK` 才表示通过。

Top-1 使用新输出路径，是因为历史分析文件保存了旧分析脚本的指纹。当前脚本会拒绝覆盖内容不同的旧结果。已有数值未因此改变；后续修改分析脚本时，也应使用新的输出路径，保留历史文件。

离线复算只验证已保存结果，不等于重新安装全部环境并在线复现实验。在线重跑可能产生费用，需要另行准备依赖和有效 API 凭据，并使用对应批次的协议与历史代码；不要用当前默认配置覆盖旧运行。不要将 API Key 放入代码、数据或提交记录。

## 数据与分析入口

| 内容 | 入口 |
| --- | --- |
| 技术报告与完整限制 | [中文技术报告](research/fixedskilllab_paper_draft_2026-10-09.md) |
| 主张、原始记录和协议的对应关系 | [主张—证据表](research/fixedskilllab_claim_evidence_2026-10-09.md) |
| ALFWorld 两批主结果 | [v5 记录](../results/formal_v5/alfworld-v5-test-30x3.jsonl)、[v8 记录](../results/formal_v8/alfworld-v8-confirm-20x3.jsonl) |
| ScienceWorld 两批主结果 | [v11b 记录](../results/formal_scienceworld_v11/scienceworld-v11b-confirm-18x3.jsonl)、[v13b 记录](../results/formal_scienceworld_v13b/scienceworld-v13b-oracle-mechanism-6x3.jsonl) |
| 强语义检索执行记录 | [Top-3](../results/scienceworld_strong_confirm_6x3.jsonl)、[Top-1](../results/scienceworld_top1_pilot.jsonl) |
| 内容对照与分析 | [原始记录](../results/scienceworld_content_dev/episodes.jsonl)、[结题分析](research/scienceworld_content_closeout_2026-10-08.md) |
| 离线检索排名 | [排名 JSONL](../results/scienceworld_retrieval_baselines_2026-09-24/rankings.jsonl)、[方法说明](research/scienceworld_retrieval_baselines_2026-09-24.md) |

早期部分预算、模型后台版本和环境状态字段缺失，不能通过新运行追补为历史事实。Procedure holdout 的完整原始总账未纳入公开快照，因此未进入七批主效果表。各报告的版本和使用范围应分别核对。

## 复用范围

可复用的部分包括 Agent 工具循环、客观评分接口、固定 Skill 条件控制、轨迹记录，以及实际加载与执行成本的离线核对。新实验应使用独立运行标识、数据输出和事前确定的评价条件，不与旧记录混算。

仓库包含 [MIT LICENSE](../LICENSE)。ALFWorld、ScienceWorld、检索模型及其他第三方资源保留各自的许可与引用要求；本项目的许可证不替代它们的授权。
