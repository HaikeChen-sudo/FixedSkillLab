# 固定 Skill 注入对工具型 LLM Agent 的初步评估

## 技术摘要

本报告记录一个用于 Agent Skill 评估的 Mini Lab 原型。环境提供 16 个确定性工具，任务成功由程序检查文件状态或结构化提交值，模型不接触 grader，也不对自己评分。研究问题是：在相同模型、相同工具和相同任务下，固定 Skill 的不同加载策略是否能提高任务成功率，或在同等成功率下减少推理成本。

目前结论是：实验管线、客观评分、Skill 注入、检索记录和成本记录均已跑通；但两轮 Pilot 中所有条件均达到 100% 成功率。因此，Mini Lab 当前只能支持“推理成本微基准”和“实验管线验证”，不能支持“Skill 提高成功率”的结论。继续在该环境运行大规模正式实验没有统计价值。

## 1. 研究目标与边界

本阶段研究固定人工 Skill 对工具型语言模型 Agent 的影响。研究对象不是自动学习 Skill、Skill 自进化、PPO 或 Skill graph。这样做是为了先固定变量：模型、工具、任务、评分器和 Skill 库都保持不变，只改变 Agent 获得哪些 Skill。

研究问题包括：

1. 给 Agent 加载所有 Skill，是否能提高成功率？
2. 只加载检索到的少量 Skill，能否以更低上下文成本达到相同或更高成功率？
3. 已知正确 Skill 的 Oracle 条件能带来多大上界收益？

## 2. Mini Lab 系统

### 2.1 环境与客观评分

Mini Lab 由 Python 标准库实现，当前包含 16 个工具：文件读写、复制移动、文本搜索替换、CSV 转换、排序、筛选、极值、求和、计数、计算和 `submit`。每个 episode 都在隔离临时目录中执行。

评分器只检查两类可观察状态：

- 文件输出是否与预期文本、CSV 或 JSON 完全一致；
- `submit(value)` 保存的原生 JSON 值是否与预期相等。

模型只能提出工具调用；工具结果由宿主程序回传；最终 `success` 由环境计算。模型看不到成功条件，也无法调用评分函数。

提交任务额外公开 `answer_json_type`，只说明答案应是 `string`、`number`、`array` 等类型，不公开答案值。该约束修复了一个已发现的协议错误：四位访问码 `"7319"` 曾被模型提交成数值 `7319`，导致客观评分失败。

### 2.2 任务与 Skill

环境当前有 58 道确定性任务：8 道文本任务、8 道计算任务、12 道 CSV 任务、12 道原组合任务和 18 道 `hard-*` 链式任务。每题包含私有参考操作，仅用于本地 `self-check` 验证任务与评分器一致。

Skill 库固定为 30 个手工 Skill。每个 Skill 采用统一结构：

```text
Name
Description
Activation Condition
Procedure
Termination Condition
```

例如，`filter-then-convert` 指定先把 CSV 筛选到临时文件，再转换为 JSON；`copy-then-customize` 指定先复制模板，只在副本中替换占位符。每个任务有人工冻结的 Gold Skill 标签，供 Oracle 条件使用。

### 2.3 Agent 与记录

Agent 以 DeepSeek Chat Completions function calling 循环运行。每次模型调用可以返回工具调用；宿主执行工具后再把 JSON 结果传回模型。每个 episode 追加保存到 `results/results.jsonl`，字段包括：

- `task_id`、`condition`、`repeat`、`success`；
- 输入、输出和总 Token；
- LLM 调用数、工具调用数、延迟和估算成本；
- 已加载 Skill、检索结果、Gold Skill 和检索排名；
- 失败或成功的完整工具轨迹。

## 3. 实验条件

五组条件使用同一模型、同一温度、同一工具、同一任务和同一 grader：

| 条件 | Skill 提供方式 |
|---|---|
| No Skill | 不加载任何 Skill，是普通 Agent baseline。 |
| All Skills | 加载全部 30 个固定 Skill。 |
| Flat Retrieval | 仅用 Skill 名称和描述进行本地哈希向量检索，加载 Top-3 Skill。 |
| Body-aware Retrieval | 检索时纳入完整 Procedure，加载 Top-3 Skill。 |
| Oracle Skill | 直接加载该题人工标注的 Gold Skill。 |

Flat 与 Body-aware 目前使用 `hash-embedding-v1`。它是无依赖、可复现的本地检索基线，不是预训练语义 embedding。因此，本报告不把它的结果解释为“语义检索模型”的结论。

## 4. 指标定义

任务成功率定义为：

\[
\mathrm{SuccessRate}=\frac{\text{成功 episode 数}}{\text{总 episode 数}}
\]

总 Token 为输入与输出 Token 之和。端到端延迟从 Agent 发起请求到完成 episode 计时。成本按照运行脚本中固定的 DeepSeek 模型单价表估算。为便于比较，额外记录：

\[
\mathrm{Efficiency}=\frac{\mathrm{SuccessRate}}{\mathrm{AverageTotalTokens}/1000}
\]

该效率指标只是当前阶段的描述性指标，不应视为统一效用函数。

## 5. 实验结果

### 5.1 v3：提交类型协议修复后的管线验证

`v3-answer-types` 使用 10 道任务。结果文件中每个条件有 60 条记录、共 300 条记录，但 `repeat` 只有 `0, 1, 2` 三个值，说明同一 `run_id` 被重复启动并追加了两批数据。它不能被当作“6 次独立重复”的正式统计样本；本节只把它作为协议修复后的管线验证。

| 条件 | 成功率 | 平均总 Token | 平均延迟 | 每成功题估算成本（USD） |
|---|---:|---:|---:|---:|
| No Skill | 100% | 5,165.6 | 4.76 s | 0.0001271 |
| All Skills | 100% | 10,866.5 | 4.35 s | 0.0001760 |
| Flat Retrieval | 100% | 4,994.8 | 4.18 s | 0.0001142 |
| Body-aware Retrieval | 100% | 5,302.5 | 4.24 s | 0.0001186 |
| Oracle Skill | 100% | 4,052.5 | 3.70 s | 0.0000885 |

提交类型错误在该 run 中未再出现，失败矩阵为空。所有条件均成功，因而不能比较质量；可以比较成本。All Skills 的平均 Token 约为 No Skill 的 2.10 倍，却没有成功率收益。Oracle Skill 的 Token 和成本最低，说明若能提供合适的 Procedure，存在上下文效率上界。

### 5.2 v4：多步骤任务 Pilot

为增加组合难度，新增 18 道 `hard-*` 任务，并固定 `v4` 任务集为 30 道题。Pilot 的 `run_id` 为 `v4-pilot-10x1`，先选其中 10 道较长的链式任务，运行 `10 tasks × 5 conditions × 1 run = 50 episodes`。

| 条件 | 成功率 | 平均总 Token | 平均延迟 | 每成功题估算成本（USD） |
|---|---:|---:|---:|---:|
| No Skill | 100% | 8,091.7 | 7.55 s | 0.0002321 |
| All Skills | 100% | 16,897.4 | 7.84 s | 0.0005499 |
| Flat Retrieval | 100% | 8,535.5 | 7.47 s | 0.0002343 |
| Body-aware Retrieval | 100% | 9,175.0 | 8.71 s | 0.0002415 |
| Oracle Skill | 100% | 7,583.7 | 7.83 s | 0.0002077 |

失败矩阵仍为空。与 v3 相比，v4 的平均 Token 和延迟明显增加，说明任务确实变长；但成功率仍完全饱和。All Skills 的成本约为 No Skill 的 2.37 倍，且没有质量收益。Flat Retrieval 和 Body-aware Retrieval 也未优于 No Skill；Oracle 仍是成本最低的条件。

## 6. 结果解释

本阶段最可靠的结论有两个。

第一，Mini Lab 的实验协议是可用的。任务评分由程序完成，Skill 加载、检索记录、运行轨迹、Token、延迟和成本均可被自动保存。提交类型协议已经覆盖数字字符串、数值和列表等情况。

第二，在当前 16 个工具和 DeepSeek Flash 的组合下，静态 Skill 没有表现出成功率优势。All Skills 稳定增加上下文负担；Oracle Skill 在两个 Pilot 中都最省 Token 和成本，但这只是“正确 Skill 已知”的上界，不代表当前 Router 已达到该上界。

不能据此得出“Skill 无效”“Body-aware 检索更差”或“Flat Retrieval 更好”的结论。当前任务过于规整，所有条件都达到成功率上限；v4 Pilot 仅有单次运行；v3 的重复记录也混入同一个 `run_id`。这些问题使得成功率差异不可识别，均值也不应报告为 `mean ± std`。

## 7. 失败分析状态

失败矩阵脚本已实现，会按 `task_id × condition` 输出失败次数、加载 Skill、Gold Skill、检索排名和工具轨迹。当前 v3 与 v4 Pilot 均无失败，因此尚不能形成有统计意义的 failure taxonomy。

后续出现失败时，建议人工逐条标注为：

| 类别 | 判定标准 |
|---|---|
| Routing Error | Retrieval 条件没有检索到 Gold Skill。 |
| Execution Error | 正确 Skill 已加载，但模型未按 Procedure 完成任务。 |
| Skill Interference | 多个加载 Skill 导致冲突、重复或错误的操作序列。 |
| Tool Error | 轨迹包含无效工具、错误参数或工具调用失败。 |
| Skill Quality Error | Gold Skill 的 Procedure 本身缺失、模糊或不正确。 |

## 8. 局限性与下一步

Mini Lab 应定位为“实验管线验证与推理成本微基准”，而不是最终 benchmark。主要限制是：

- 工具接口规则、操作空间小，DeepSeek Flash 可以稳定完成；
- 固定题目和固定文件内容不能充分覆盖未见状态；
- Gold Skill 由人工标注，尚未做双人标注或一致性检查；
- 当前 Router 是哈希检索基线，不代表强语义检索器；
- v4 Pilot 只有每题每条件一次，不能估计随机性。

下一阶段建议迁移到 ALFWorld 的 text-only 环境。ALFWorld 以自然语言观察和动作组成交互 episode，Agent 需要在部分可见状态中移动、打开容器、取放物体并完成家务目标；环境直接给出完成信号。应先完成以下最小步骤：

1. 跑通一个 text-only ALFWorld episode，并把原始观察、动作、环境奖励和完成状态写入 JSONL；
2. 保持 A–E 五组设计不变，只把 Mini Lab 工具循环替换为 ALFWorld 动作循环；
3. 为 ALFWorld 手写 5～10 个固定导航和物体操作 Skill；
4. 先跑 `10 tasks × 5 conditions × 1 run` Pilot；
5. Pilot 证明存在成功率差异后，再冻结任务并运行 `30 tasks × 5 conditions × 3 runs`。

## 参考资料

1. Shridhar, M., Yuan, X., Côté, M.-A., et al. *ALFWorld: Aligning Text and Embodied Environments for Interactive Learning*. ICLR, 2021. https://arxiv.org/abs/2010.03768
2. *HiSkill: Empowering LLM Agents with Hierarchical Skill Graphs*. 用户提供的论文 PDF。
3. *Skill-Pro: Learning Reusable Skills from Experience via Non-Parametric PPO for LLM Agents*. 用户提供的论文 PDF。
4. *SkillRouter: Skill Routing for LLM Agents at Scale*. 用户提供的论文 PDF。

## 复现信息

- 代码：`minilab.py`、`agent.py`、`skills.py`、`tasks.py`、`gold_skills.py`、`retrieval.py`、`experiment.py`
- 原始 episode 记录：`results/results.jsonl`
- 汇总脚本：`summarize_results.py`
- 失败矩阵：`failure_matrix.py`
- 运行配置：DeepSeek Flash、temperature = 0、thinking disabled
