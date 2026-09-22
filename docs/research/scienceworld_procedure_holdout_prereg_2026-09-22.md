# ScienceWorld Procedure-only 独立检验：执行前登记

日期：2026-09-22。状态：候选协议已写好，本机只运行了离线预览和测试。**尚未读取这六道 test variation 的题目或轨迹，尚未调用 DeepSeek。** 执行前需先提交本文件、代码和 [机器清单](../../results/scienceworld_procedure_holdout_manifest.json)，再由程序向 ScienceWorld 核对官方 test split。核对失败就停止，不换题。

## 问题和题目

本次只问一件事：在同一 Agent、控制器和任务下，改写固定 Skill 的 Procedure 是否改变任务完成和过程执行。P0/P1 沿用 [开发 Pilot](scienceworld_procedure_pilot_prereg_2026-09-22.md)的原文，不根据新题调整。化学组的 P1 明确 `read recipe` 和 `mix <container>`；斜面组的 P1 要求比较两次测得的时间后再选择斜面。每一组内，Name、Description、Activation 和 Termination 相同。

另一个 v14 设计已预留化学 v024–v026、斜面 v126–v128。本次按编号取各自后续三个候选：

| 任务类型 | 候选 test variation | 本地既有结果 |
|---|---|---|
| `chemistry-mix` | v027、v028、v029 | 未找到对应 episode |
| `inclined-plane-determine-angle` | v129、v130、v131 | 未找到对应 episode |

安装包中的分组逻辑与先前登记的 variation 数量支持这些编号属于 test 段；本机启动 Java 网关核对时停滞，故目前仍称“候选”。[执行器](../../scienceworld_procedure_holdout.py)会在第一笔模型调用前运行 `get_variations_test()`，逐题核对；只有六题均通过才继续。查找候选时未查看这些题的内容，也未以预期难度或模型表现筛选。

## 固定运行协议

同一 `deepseek-v4-flash`、temperature 0、ScienceWorld `easy`、v14b Agent 提示和 shared-state-checkpoint-v1 控制器。每题最多 100 次 Agent 动作。每个 variation 跑 P0、P1 各三次，共 6 × 2 × 3 = 36 个 episode；同题同 repeat 的条件顺序由种子 20260922 确定。两条件都走 `oracle_v4` 的同一 Skill 加载路径，执行器只临时替换该 Skill 的 Procedure，原库在 episode 后恢复。每条记录保存 Skill 提示哈希、协议清单哈希、Token、费用及完整动作轨迹。

记录费用累计达到 0.10 美元时，执行器在下一个 episode 前停止；最后一个 episode 可使总额略超。API 中断后用同一 run-id 续跑，保留已完成记录，不择优重跑。清单或已存记录不符时拒绝续跑。费用上限导致缺题时只报告“未完成”，不算两组胜负。

## 预先固定的判定

环境成功只看 `score >= 100`。过程完成使用现有、已冻结的只读审计代码：

- 化学：模型读到配方内容，随后执行使环境分数上升的 `mix`，最后才 `focus`；三件事按此顺序发生。
- 斜面：对两块斜面各做一次完整测量。每次需放木块、启动秒表、在计时中观察木块到底、读取到底后的秒表并停表。审计另记两次最终时间是否不同，以及选择是否由较长时间支持；时间相同或没有足够记录时，选择证据记为“无法判断”，不硬判正确。

按任务类型分别报告 P0/P1 的环境成功数、过程完成数、平均 Input Tokens、Output Tokens、Total Tokens、端到端延迟、Cost per Successful Task、环境分数和动作数。费用指标按**该条件全部 episode 的 API 成本 ÷ 成功 episode 数**计算；成功数为零时记未定义。再列出每个 variation 内三次配对的成功、过程与 Total Tokens 差值。三次运行是同题重复，不是十八道独立题；六个 variation 不足以支持对整个 ScienceWorld 的显著性或普遍化结论。

我们只在两类任务中都看到 P1 的过程完成率高于 P0，且环境成功率均未下降时，才描述为“这六题支持 Procedure 改写改善过程执行”。若只有一类改善，就限定在该类。若过程未改善，即使 Token 更低，也不把节省成本写成过程效果。环境成功与成本分别报告，不用单一分数掩盖取舍。原 v14 预留的六题保持不动；本次结果不能用于回改 v14 Skill 后再把 v14 当独立确认。

## 执行前状态

离线预览生成 36 个唯一 episode，相关 15 项本地测试通过，API 调用数为 0。执行器与[分析器](../../scienceworld_procedure_holdout_analysis.py)已写好。还差两步：提交协议快照；在用户本机完成官方 test split 核对并启动付费运行。分析器会拒绝缺失、重复、跨清单或 Token 对账错误的记录。
