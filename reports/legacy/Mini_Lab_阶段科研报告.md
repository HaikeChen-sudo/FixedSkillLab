# 固定 Skill 注入对工具型 LLM Agent 的初步评估

本文由已发布 PDF 对应的 Word 原稿转换，并逐段、逐单元格核对 PDF。保留当时的数据、表述和后续计划；不代表最新结论。当前综合说明见[项目说明与结果复核](../../docs/PROJECT_SUMMARY.md)。

Mini Lab 阶段性技术报告

| 研究阶段 | 第一阶段：Mini Lab 与固定 Skill 实验 |
| --- | --- |
| 报告性质 | 阶段性技术报告，不作为正式 benchmark 结论 |
| 实验模型 | DeepSeek Flash，temperature = 0，thinking disabled |
| 数据来源 | results/results.jsonl；代码与评分器为当前工作区版本 |

## 摘要

本报告记录一个用于评估 Agent Skill 的 Mini Lab 原型。环境提供 16 个确定性工具，任务是否成功由程序检查文件状态或结构化提交值决定，模型不接触 grader，也不对自己评分。研究目标是比较固定 Skill 的不同加载方式：它们是否提高任务成功率，或在同等成功率下减少推理成本。

当前结果说明，实验管线已经可用：客观评分、Skill 注入、检索记录、轨迹、Token、延迟和成本都能自动保存。但两轮 Pilot 中所有条件均达到 100% 成功率。因此，Mini Lab 当前只能支持“实验管线验证”和“推理成本微基准”，不能支持“Skill 提高成功率”的结论。继续在该环境直接跑 450 条正式实验，价值不高。

## 研究问题与边界

本阶段只研究固定人工 Skill 对工具型语言模型 Agent 的影响。模型、工具、任务、评分器和 Skill 库保持不变，只改变 Agent 获得哪些 Skill。没有引入自动学习 Skill、Skill 自进化、PPO 或 Skill graph，目的是先把变量控制住。

加载全部 Skill，是否能提高任务成功率？

只加载检索到的少量 Skill，能否以更低上下文成本达到相同或更高成功率？

已知正确 Skill 的 Oracle 条件，能给出多大的效率上界？

## 2. 系统设计

### 2.1 客观环境与评分

Mini Lab 用 Python 标准库实现。它包含文件读写、复制移动、文本搜索替换、CSV 转换、排序、筛选、极值、求和、计数、计算和提交答案等 16 个工具。每个 episode 在隔离目录中运行。

评分器只读取实际状态：一类是输出文件是否与预期文本、CSV 或 JSON 一致；另一类是 submit 保存的原生 JSON 值是否与预期相等。模型只能提出工具调用，工具结果由宿主程序回传，最终 success 由环境计算。

为避免“数字字符串”被误交为数值，任务会公开答案 JSON 类型，例如 string、number 或 array，但不公开正确答案。访问码 "7319" 这一类值因此会按字符串提交。

### 2.2 任务与固定 Skill

当前环境有 58 道确定性任务：文本任务 8 道、计算任务 8 道、CSV 任务 12 道、原组合任务 12 道，以及新增的 hard 链式任务 18 道。每题都有私有参考操作，仅用于 self-check 验证任务定义与评分器一致。

Skill 库固定为 30 个手工 Skill。每个 Skill 都有 Name、Description、Activation Condition、Procedure 和 Termination Condition 五个字段。例如，filter-then-convert 要求先筛选 CSV 到临时文件，再转换为 JSON；copy-then-customize 要求先复制模板，只修改副本。每题另有人工冻结的 Gold Skill 标签，供 Oracle 条件使用。

### 2.3 Agent 循环与结果记录

Agent 通过 DeepSeek Chat Completions 的 function calling 循环工作：模型返回工具调用，宿主执行工具并回传 JSON 结果，直到模型提交答案或停止。每个 episode 追加写入 results/results.jsonl，记录任务、条件、重复编号、成败、Token、延迟、成本、加载 Skill、检索排名和完整轨迹。

## 3. 实验条件与指标

| 条件 | Skill 提供方式 |
| --- | --- |
| No Skill | 不加载任何 Skill，是普通 Agent baseline。 |
| All Skills | 加载全部 30 个固定 Skill。 |
| Flat Retrieval | 只使用 Skill 名称和描述检索，加载 Top-3 Skill。 |
| Body-aware Retrieval | 检索时纳入完整 Procedure，加载 Top-3 Skill。 |
| Oracle Skill | 直接加载人工标注的 Gold Skill。 |

Flat 与 Body-aware 当前使用 hash-embedding-v1。这是无依赖、可复现的本地检索基线，不是预训练语义 embedding。因此，结果不能被解释为强语义检索器的结果。

核心指标为任务成功率、平均输入 Token、平均输出 Token、平均总 Token、端到端延迟和每成功题估算成本。效率指标定义为成功率除以平均总 Token（以千 Token 为单位）；它只是当前阶段的描述性指标，不是统一效用函数。

## 4. 实验结果

### 4.1 v3：提交类型协议修复后的管线验证

v3-answer-types 使用 10 道任务。结果文件中每个条件有 60 条记录，共 300 条记录，但 repeat 只有 0、1、2 三个值。这说明同一个 run_id 被重复启动并追加了两批数据。它不能被当作 6 次独立重复的正式统计样本，本节只把它作为协议修复后的管线验证。

| 条件 | 成功率 | 平均总 Token | 平均延迟 | 每成功题成本（USD） |
| --- | --- | --- | --- | --- |
| No Skill | 100% | 5,165.6 | 4.76 s | 0.0001271 |
| All Skills | 100% | 10,866.5 | 4.35 s | 0.0001760 |
| Flat Retrieval | 100% | 4,994.8 | 4.18 s | 0.0001142 |
| Body-aware | 100% | 5,302.5 | 4.24 s | 0.0001186 |
| Oracle | 100% | 4,052.5 | 3.70 s | 0.0000885 |

提交类型错误在 v3 中未再出现，失败矩阵为空。所有条件均成功，因此不能比较质量；可以比较成本。All Skills 的平均 Token 约为 No Skill 的 2.10 倍，却没有成功率收益。Oracle 的 Token 和成本最低，说明正确的 Procedure 可能带来上下文效率收益。

### 4.2 v4：多步骤任务 Pilot

v4 新增 18 道 hard 链式任务，并固定 30 题实验集。Pilot 的 run_id 为 v4-pilot-10x1，先选 10 道较长任务，运行 10 tasks × 5 conditions × 1 run，共 50 个 episode。

| 条件 | 成功率 | 平均总 Token | 平均延迟 | 每成功题成本（USD） |
| --- | --- | --- | --- | --- |
| No Skill | 100% | 8,091.7 | 7.55 s | 0.0002321 |
| All Skills | 100% | 16,897.4 | 7.84 s | 0.0005499 |
| Flat Retrieval | 100% | 8,535.5 | 7.47 s | 0.0002343 |
| Body-aware | 100% | 9,175.0 | 8.71 s | 0.0002415 |
| Oracle | 100% | 7,583.7 | 7.83 s | 0.0002077 |

v4 的平均 Token 和延迟高于 v3，说明任务更长；但失败矩阵仍为空，所有条件仍然成功。All Skills 的每成功题成本约为 No Skill 的 2.37 倍，没有质量收益。Flat 与 Body-aware 也没有优于 No Skill。Oracle 仍是成本最低的条件。

## 5. 结果说明什么，以及不说明什么

最可靠的结论是，Mini Lab 的实验协议已经可用：客观评分、Skill 注入、检索记录、运行轨迹、Token、延迟和成本均能自动保存。提交类型协议也已覆盖数字字符串、数值和列表等情况。

同时，当前 16 个工具与 DeepSeek Flash 的组合对模型过于规整。静态 Skill 没有表现出成功率优势；All Skills 稳定增加上下文负担；Oracle 在两轮 Pilot 中都最省 Token 和成本，但它只是“正确 Skill 已知”时的上界。

因此，不能据此说 Skill 无效、Body-aware 检索更差，或 Flat Retrieval 更好。任务成功率已经饱和，差异无法被观察；v4 Pilot 只有一次运行；v3 的记录又混入了重复启动的数据。当前不应报告 mean ± std，也不应把这些均值写成正式 benchmark 结论。

## 6. 失败分析与风险

失败矩阵脚本会按 task_id × condition 输出失败次数、加载 Skill、Gold Skill、检索排名和工具轨迹。v3 与 v4 Pilot 都没有失败，因此暂时不能形成有统计意义的失败分类。未来有失败时，建议按下表人工标注。

| 类别 | 判定标准 |
| --- | --- |
| Routing Error | 检索条件没有检索到 Gold Skill。 |
| Execution Error | 正确 Skill 已加载，但模型未按 Procedure 完成任务。 |
| Skill Interference | 多个加载 Skill 导致冲突、重复或错误操作。 |
| Tool Error | 轨迹包含无效工具、错误参数或工具调用失败。 |
| Skill Quality Error | Gold Skill 的 Procedure 本身缺失、模糊或不正确。 |

## 7. 局限性与下一步

工具接口规则、操作空间小，DeepSeek Flash 可以稳定完成任务。

固定题目和固定文件内容不能充分覆盖未见状态。

Gold Skill 由人工标注，尚未做双人标注或一致性检查。

当前 Router 是哈希检索基线，不代表强语义检索器。

v4 Pilot 每题每条件只运行一次，不能估计随机性。

下一阶段建议迁移到 ALFWorld 的 text-only 环境。ALFWorld 用自然语言观察和动作组成交互 episode，Agent 需要在部分可见状态中移动、打开容器、取放物体并完成目标，环境直接给出完成信号。它比当前工具环境更适合观察规划、检索和执行错误。

跑通一个 text-only ALFWorld episode，并把观察、动作、奖励和完成状态写入 JSONL。

保持 A–E 五组设计不变，只把工具循环替换为 ALFWorld 动作循环。

手写 5～10 个固定导航与物体操作 Skill，再跑 10 tasks × 5 conditions × 1 run Pilot。

Pilot 出现可观察的成功率差异后，再冻结任务并运行 30 tasks × 5 conditions × 3 runs。

## 参考资料

[1] Shridhar, M., Yuan, X., Côté, M.-A., et al. ALFWorld: Aligning Text and Embodied Environments for Interactive Learning. ICLR, 2021. https://arxiv.org/abs/2010.03768

[2] HiSkill: Empowering LLM Agents with Hierarchical Skill Graphs. 提供的论文 PDF。

[3] Skill-Pro: Learning Reusable Skills from Experience via Non-Parametric PPO for LLM Agents. 提供的论文 PDF。

[4] SkillRouter: Skill Routing for LLM Agents at Scale. 提供的论文 PDF。
