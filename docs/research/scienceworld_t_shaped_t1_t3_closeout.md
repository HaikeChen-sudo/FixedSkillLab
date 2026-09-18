# ScienceWorld T 型 Skill 组合：T1–T3 开发实验结题记录

2026-09-18

## 摘要

三轮实验都没有观察到横向层与纵向 Skill 在任务成功率上的正向互补。T1 的交互效应为 −8.3 个百分点；T2、T3 均为 −16.7 个百分点。T3 的组合组比纵向组少用 16.9% 的 Total Tokens，但两组都成功 4/6，未达到事先冻结的成功率和交互效应门槛。项目停止在这两个开发任务上继续调整横向层。

这一结果只适用于本项目测试的横向文本与两版控制器、DeepSeek-v4-flash、ScienceWorld 任务及当前执行协议。它不能证明所有 T 型结构无效。纵向 Procedure 的效果和横向层的成本效果需要分别报告，不能用它们替代“组合互补”的证据。

## 研究问题与判定

实验把横向层定义为跨任务复用的执行指导或确定性控制，把纵向层定义为任务专用 Procedure。每轮使用相同的 2×2 因子设计：No Skill（N）、Horizontal-only（H）、Vertical-only（V）、Full（H+V）。Agent 根据预先固定的任务标签加载 Skill，不经过检索器。模型为 `deepseek-v4-flash`，temperature 为 0；每个 episode 最多调用工具 400 次。ScienceWorld 环境分数达到 100 才算成功，模型不参与评分。

组合互补按成功率交互效应计算：

\[
\Delta_{int}=(SR_{Full}-SR_V)-(SR_H-SR_N).
\]

研究假设要求 \(\Delta_{int}>0\)，且 Full 成功率高于单独使用纵向层。T1 是实现与方向 Pilot；T2 和 T3 复用 T1 中已观察到分歧的 `melt:v025`、`freeze:v026`，均是定向开发实验。T3 另行冻结成本门槛：Full 的平均 Total Tokens 不超过 Vertical 的 1.25 倍。三次重复是同一 task variation 的重复运行，不是六个独立任务。

## 三轮横向层

| 实验 | 横向层 | 纵向层 | 任务与运行 |
|---|---|---|---|
| T1 | 固定的跨任务执行 Skill 文本 | 固定任务 Procedure | 12 个 task variation，各条件 1 次，共 48 episodes |
| T2 | T1 横向文本 + 按分数拦截重复动作的控制器 | 与 T1 相同 | 2 个已见 variation，各条件 3 次，共 24 episodes |
| T3 | 仅确定性检查点控制器：连续等待 3 次后要求观察；其他命令在分数和 observation 均不变时才拦截 | 与 T1 相同 | 同 2 个已见 variation，各条件 3 次，共 24 episodes |

T3 的 Full 与 Vertical 加载相同的纵向 Skill 文本；逐任务 Prompt 哈希一致。两组唯一有意设置的差别是横向控制器。控制器不能直接看到隐藏温度，只能要求 Agent 执行 `examine`、`look around` 或 `inventory` 等观察命令。因此“状态感知”指观察检查点，不等于读取完整环境状态。

## 结果

下表中的 Token、得分和时间都是每个 episode 的平均值，展示值已四舍五入。成功成本为该条件全部 episode 的估算 API 成本之和除以成功 episode 数；没有成功样本时不定义。三轮任务组成和运行时点不同，不合并成功率，也不直接比较跨轮绝对成本。

| 实验 | 条件 | 成功 | 平均得分 | Input Tokens | Output Tokens | Total Tokens |
|---|---|---:|---:|---:|---:|---:|
| T1 | No Skill | 10/12 | 90.9 | 481,235 | 2,218 | 483,452 |
| T1 | Horizontal | 11/12 | 95.7 | 330,325 | 2,447 | 332,772 |
| T1 | Vertical | 11/12 | 95.3 | 367,242 | 2,075 | 369,316 |
| T1 | Full | 11/12 | 95.3 | 363,756 | 2,036 | 365,792 |
| T2 | No Skill | 1/6 | 60.7 | 2,078,158 | 9,527 | 2,087,685 |
| T2 | Horizontal | 1/6 | 58.2 | 6,369,459 | 34,980 | 6,404,439 |
| T2 | Vertical | 5/6 | 91.3 | 695,967 | 4,060 | 700,026 |
| T2 | Full | 4/6 | 82.3 | 1,501,870 | 10,569 | 1,512,438 |
| T3 | No Skill | 0/6 | 45.5 | 2,581,699 | 8,589 | 2,590,288 |
| T3 | Horizontal | 1/6 | 55.8 | 2,527,388 | 19,610 | 2,546,998 |
| T3 | Vertical | 4/6 | 88.3 | 1,433,031 | 7,432 | 1,440,464 |
| T3 | Full | 4/6 | 82.7 | 1,186,394 | 10,024 | 1,196,418 |

| 实验 | 条件 | 延迟（秒） | 成功成本（美元） | Tool Calls | 环境步数 |
|---|---|---:|---:|---:|---:|
| T1 | No Skill | 54.9 | 0.004132 | 53.2 | 80.3 |
| T1 | Horizontal | 49.4 | 0.003209 | 46.0 | 63.1 |
| T1 | Vertical | 52.1 | 0.003275 | 47.9 | 67.8 |
| T1 | Full | 45.3 | 0.003173 | 45.9 | 65.9 |
| T2 | No Skill | 247.4 | 0.080047 | 177.8 | 337.3 |
| T2 | Horizontal | 364.6 | 0.204644 | 234.3 | 324.2 |
| T2 | Vertical | 91.3 | 0.006637 | 89.3 | 130.5 |
| T2 | Full | 181.0 | 0.016481 | 137.7 | 173.2 |
| T3 | No Skill | 321.9 | 未定义 | 220.5 | 401.5 |
| T3 | Horizontal | 269.2 | 0.100541 | 150.2 | 229.7 |
| T3 | Vertical | 218.3 | 0.014621 | 133.2 | 235.8 |
| T3 | Full | 176.3 | 0.013778 | 111.7 | 137.2 |

| 实验 | Full − Vertical 成功率 | \(\Delta_{int}\) | 预定判定 |
|---|---:|---:|---|
| T1 | 0 个百分点 | −8.3 个百分点 | Pilot 未显示组合增量；不作确认性结论 |
| T2 | −16.7 个百分点 | −16.7 个百分点 | 未达到 Full 高于单层组的开发门槛 |
| T3 | 0 个百分点 | −16.7 个百分点 | 成功率与交互门槛失败；Token 门槛通过 |

T1 的六个跨领域 case 四组全部成功，存在成功率天花板，无法检验横向迁移。T2 的 `melt:v025` 中，Vertical 成功 3/3，Full 成功 1/3；`freeze:v026` 中则是 2/3 对 3/3。T3 在同两题上分别为 `melt` 2/3 对 1/3、`freeze` 2/3 对 3/3。横向层对两类任务的方向相反，当前数据不支持稳定的跨任务收益。

T3 Full 的平均 Total Tokens 为 Vertical 的 0.83 倍，平均延迟少 42.0 秒，成功成本低约 5.8%。这些是同一开发集上的描述性成本差异。它们没有改变成功率门槛未通过的判定；如果以后单独研究控制器节约成本，需要新协议和未参与调参的任务。

## 解释与边界

T2 的控制器确实拦截了重复动作，但它主要依据分数判断停滞。ScienceWorld 中样本可能继续升温或降温而分数暂时不变，所以分数不变不能证明等待无效。轨迹支持这一机制疑点，不能仅凭两题断定所有失败都由控制器造成。T3 改为要求显式观察，降低了平均成本，却仍未增加 Full 的成功数。

本研究只测试了三种横向实现。T1 一次运行，T2/T3 只有两个经过选择的 task variation；即使每题重复三次，独立任务数仍是两个。各轮 No Skill 结果也有波动。因此报告保留每轮内部对照，不汇总成一个“大样本 T 型成功率”，不作跨模型或整个 ScienceWorld 的结论。

## 项目决策

按 T3 冻结的失败规则，项目停止在 `melt:v025`、`freeze:v026` 上继续调横向层，也不进入原定的 T 型 Router 或 Flat-matched 确认阶段。后续研究分别处理已观察到的纵向 Procedure 效果与 Skill 检索的质量—成本问题。T3 的控制器成本差异可留作独立线索，不能事后改写为 T 型成功。

## 数据与复核

三轮分别保留 48、24、24 条唯一 episode，冻结数据的 SHA-256 与各自审计 manifest 一致。报告数字来自冻结 JSONL；成功数、Token 和成本已另行从 episode 字段重算。

- T1：[协议](../../results/scienceworld_t1_t_shaped_pilot_manifest.json)、[审计汇总](../../results/formal_scienceworld_t1/analysis_summary.json)、[冻结 episodes](../../results/formal_scienceworld_t1/scienceworld-t1-t-shaped-pilot-12x1.jsonl)
- T2：[协议](../../results/scienceworld_t2_controller_dev_manifest.json)、[审计汇总](../../results/formal_scienceworld_t2/analysis_summary.json)、[冻结 episodes](../../results/formal_scienceworld_t2/scienceworld-t2-controller-dev-2x3.jsonl)
- T3：[协议](../../results/scienceworld_t3_state_aware_dev_manifest.json)、[审计汇总](../../results/formal_scienceworld_t3/analysis_summary.json)、[冻结 episodes](../../results/formal_scienceworld_t3/scienceworld-t3-state-aware-dev-2x3.jsonl)
