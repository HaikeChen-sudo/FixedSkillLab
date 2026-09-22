# ScienceWorld Procedure-only holdout 结案记录

日期：2026-09-22。运行编号：`scienceworld-procedure-holdout-6x3`。本记录只解释已完成的运行，不改[执行前登记](scienceworld_procedure_holdout_prereg_2026-09-22.md)、[清单](../../results/scienceworld_procedure_holdout_manifest.json)或旧评分器。原始 episode 留在本地 `results/scienceworld_results.jsonl`。

## 结论

本轮没有证实 P1 的 Procedure 改写改善任务完成或过程执行。斜面 P1 成功 8/9，P0 成功 9/9，已经不满足事先写下的“成功率不下降”条件。预登记的过程评分器还误读了新 variation，不能用其输出证明 P1 的过程收益。化学两组都成功 9/9，成功率已到天花板。

我们不在这六道 test variation 上修改 P1 后重跑确认。后续任何改版都需新编号、新协议和未使用的确认数据。

## 运行与六项核心指标

36 个 episode 对应 6 道 variation × 2 条件 × 3 次重复。36 个 `(task_id, repeat, condition)` 键各不相同；模型均为 `deepseek-v4-flash`，temperature 均为 0，最多 100 步，Agent 协议均为 `scienceworld-v14b`，控制器均为 `shared-state-checkpoint-v1`。全部记录持有相同的清单哈希，且 Input + Output = Total。程序估算的 API 成本合计 $0.07465；这不是平台账单的独立核对。

| 任务类型 | 条件 | 成功率 | 平均 Input Tokens | 平均 Output Tokens | 平均 Total Tokens | 平均端到端延迟 | 每成功任务估算成本 |
|---|---|---:|---:|---:|---:|---:|---:|
| 化学 | P0 | 9/9（100%） | 74,578 | 1,335 | 75,913 | 32.3 秒 | $0.00137 |
| 化学 | P1 | 9/9（100%） | 76,145 | 1,293 | 77,438 | 32.0 秒 | $0.00134 |
| 斜面 | P0 | 9/9（100%） | 253,481 | 2,312 | 255,793 | 60.9 秒 | $0.00289 |
| 斜面 | P1 | 8/9（88.9%） | 223,584 | 2,268 | 225,852 | 61.1 秒 | $0.00303 |

斜面 P1 的平均 Total Tokens 比 P0 少约 11.7%，但每成功任务的估算成本高约 4.7%。两组各只有三道 variation；三次重复不能当成九道独立题，也不能据此推出整个 ScienceWorld 的效果。

## 过程评分为何失效

化学评分器要求 `mix` 这一步直接加分。`chemistry-mix:v027` 的 P0 第 0 次运行先发出 `mix wood cup`，环境要求数字消歧；模型下一步输入 `4`，环境才执行混合并生成红纸。旧评分器将这次有效混合记成“未完成”。其余 17 次化学运行都通过旧判定。按实际动作顺序看，两组在这六题中的化学过程均没有可确认的差异；这项修正属于看过 test 轨迹后的诊断，不是预登记结果。

斜面评分器只识别 `wood block`，而 v130 使用 `steel block`、v131 使用 `brick`。这两题共 12 个 episode，因此旧评分器给出的 P0 0/9、P1 1/9 完整测量数不能作为有效比较。旧评分器还把“选用时更久的斜面”固定为正确选择；v129、v131 的任务要求找**最陡**，应在两次完整测量后比较较短时间。按物体名称做事后归一化时，完整双斜面测量为 P0 1/9、P1 2/9；这个敏感性结果同样不作确认性证据。

原 Skill 的 Description、Activation 和 Termination 都限定“最浅”，而 v129、v131 要求“最陡”。两条件加载相同的不匹配说明，所以相互比较的 Agent 配置仍一致；但我们不能称这两题使用了正确适用范围的 Oracle Skill。新题暴露的是实验设计缺陷，不能通过只修评分代码来消除。

## 唯一失败 episode

斜面 `v131`、repeat 1、P1 的环境分数为 −100。模型在 H 斜面的砖尚未到达底部时读到 7 ticks 并停表；C 斜面后来完整测得 22 ticks。模型聚焦 H，环境判错。同题同次的 P0 完整测得 C 为 21 ticks、H 为 42 ticks，随后聚焦 C，环境给 100 分。P1 的失败轨迹支持“过早结束第一次测量”这一具体执行问题，不能把单次失败归因于 Procedure 文本本身。

## 后续边界

原评分器和结果不改。[v2 过程评分器](../../scienceworld_procedure_audit_v2.py)另存为新文件，只供后续协议使用；它按环境观察确认配方和产物，识别斜面上的具体物体，并按任务中的“最陡/最浅”解释时间。合成测试及旧 dev 题 `chemistry-mix:v016`、`inclined-plane-determine-angle:v084` 的只读检查已通过。我们没有用 v2 结果替换上表或重写这次 holdout 的结论。

若继续研究这一分支，先在 train/dev 上建立同时覆盖“最陡/最浅”的共同 Skill 元数据，再只改变 Procedure。新确认集不能复用本轮六题，也不能占用另一个 v14 协议已预留的六题。当前数据不支持为这条分支立刻追加付费大实验。
