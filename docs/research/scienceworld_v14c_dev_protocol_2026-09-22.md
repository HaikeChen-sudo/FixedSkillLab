# ScienceWorld v14c：新一轮 dev-only 门检协议

日期：2026-09-22。状态：代码与候选题号已写定；尚未读取下列新 dev 题面，尚未启动 ScienceWorld 核对 split，也未调用 DeepSeek。本轮是开发检查，不是独立确认。

## 为什么开新版本

v14b 的电路 dev 题中，Body-aware 把正确 Skill 排第 4，未加载；斜面 dev 题中，Oracle 在滑块未到底时读取计时，最后选错。v14b 已对应已完成的 episode，不能原地改。本版保留原检索算法和 Agent 协议，只改两条 Skill：

| Skill | v14c 改动 | 开发依据 |
|---|---|---|
| `power-component-circuit` | Description 明确“打开指定灯泡并建立供电电路”；其他字段不变。 | v14b 电路 `v010` 的任务原文与离线排名。改后该旧 dev query 的 Body-aware Gold 排名从 4 升到 1；这是调试结果，不是新题验证。 |
| `measure-inclined-plane-angle` | Procedure 明确：观察滑块到底后再停表读数；中途读数作废，两次完整计时后才聚焦。 | v14b 斜面 `v084` 的 Oracle 轨迹；B、F 都曾在未到底时被读取。Description、Activation、Termination 不变。 |

旧 `v4b` 的库哈希仍为 `37faee802461ff8d76d7284dc832e4f71f41503fb1b044b9aa64c9ba23b4ffd4`；新 `v4c` 为 `822b7d3937611463a1fb93c11c3be37723cd7b5123e096c448e27608bcf6cbe7`。条件名称带 `_v4c`，防止与旧 episode 混算。No Skill 不加载 Skill，保持同一 Agent 协议。

## 新 dev 题与停机门槛

按各任务类型上一道 dev variation 的下一个编号选题，不依据题面或模型表现挑选：`power-component:v011`、`grow-plant:v063`、`chemistry-mix:v017`、`inclined-plane-determine-angle:v085`。先运行无 API 的检索审计；它必须逐题核对官方 dev split。若任何题不在 dev split，或 Body-aware Gold Hit@3 少于 4/4，**停止，不调用模型，也不改这四题后重跑**。

离线门槛通过后，仅跑 `body_aware_retrieval_v4c` 与 `oracle_v4c`，每题每条件一次，共 8 个 episode；`deepseek-v4-flash`、temperature 0、`easy`、最多 100 个 Agent 动作，run-id 固定为 `scienceworld-v14c-dev-check-4x1`。API 中断只续跑缺失键，不重跑已完成 episode。检查电路 Body-aware 是否命中并完成、斜面 Oracle 是否完成；同时列全 8 条的成功、Score、Input/Output/Total Tokens、延迟、估算费用和动作数。任何失败都如实保留，不把一次 dev 表现写成确认性效果。

即使本轮通过，也**不自动进入原 v14 的 12 题正式 test**。项目另一分支已使用同任务类型的化学 `v027–v029` 与斜面 `v129–v131` test variation；预留的 v14 test ID 虽不同，整个任务类型已不再完全盲测。本轮 Skill 改动只依据 v14b dev 轨迹，但后续正式研究必须如实披露这个边界，或另选真正未接触的任务类型与确认集。v14c 也不是新检索算法的原创性证据。
