# ScienceWorld v14b 新任务类型：开发集门检

日期：2026-09-22。数据来自 `results/scienceworld_results.jsonl` 中的 `scienceworld-v14b-dev-4x1`：4 道官方 dev variation × 4 条件 × 1 次，共 16 个 episode，无重复。本记录不读取 v14 预留的 12 道 test variation，也不修改旧结果。它是开发诊断，不是确认实验。

## 结果

| 条件 | 成功 | 平均 Input Tokens | 平均 Output Tokens | 平均 Total Tokens | 平均端到端延迟 | 每成功任务估算成本 |
|---|---:|---:|---:|---:|---:|---:|
| No Skill | 2/4 | 399,907 | 3,232 | 403,139 | 65.2 秒 | $0.00675 |
| Flat Top-3 | 4/4 | 112,123 | 1,363 | 113,486 | 40.6 秒 | $0.00160 |
| Body-aware Top-3 | 3/4 | 753,232 | 7,261 | 760,493 | 140.5 秒 | $0.00833 |
| Oracle v4 | 3/4 | 119,634 | 1,524 | 121,158 | 40.6 秒 | $0.00228 |

成本是程序按缓存命中／未命中和输出 Token 估算的 API 费用，不是平台账单。每组只有四道题且各跑一次；不能据此判断方法总体优劣。

| Dev 任务 | No Skill | Flat | Body-aware | Oracle | Flat / Body 的 Gold 排名 | 可核实的问题 |
|---|---:|---:|---:|---:|---|---|
| 电路 `v010` | 成功 | 成功 | 失败，83 分 | 成功 | 2 / 未进 Top-3 | Body-aware 未加载电路 Skill，单题用了 2,622,147 Total Tokens；这是检索未命中与长轨迹同时发生，不能单凭它估计因果效应。 |
| 种植 `v062` | 失败，34 分 | 成功 | 成功 | 成功 | 1 / 1 | 三个 Skill 条件都完成，本题不区分 Flat、Body-aware、Oracle。 |
| 化学 `v016` | 成功 | 成功 | 成功 | 成功 | 1 / 1 | 四组均成功，存在成功率天花板。 |
| 斜面 `v084` | 失败，−100 分 | 成功 | 成功 | 失败，−100 分 | 3 / 1 | Oracle 已加载正确标签的 Skill，但最终聚焦 B 后环境判错；Flat 聚焦 F 后得 100 分。不能将单次 Oracle 失败直接归因于 Skill 文本。 |

Body-aware 的平均 Token 主要受电路题的极长失败轨迹影响。原始记录中的 `retrieval_query`、`skills_loaded`、`gold_skill_ranks`、Token 和 `trace` 可逐项复核。这里只报告 **Gold Hit@3**：Flat 为 4/4，Body-aware 为 3/4；Oracle 不经过检索，不应计入该指标。

## 门检决定

**暂不冻结或启动 v14 的 12 题 × 4 条件 × 3 次正式 test。** 当前开发结果至少暴露两处不同层次的问题：电路题 Body-aware 路由漏掉 Gold；斜面题即使 Oracle 命中也可能失败。先在 train/dev 范围内分别处理，再重跑新的开发 Pilot。不能看预留 test 题后改 Skill、Router 或 Agent，也不能把本轮四题当独立验证。v14 检查的是新任务类型的适用边界，不是一个已经成立的原创检索算法；是否投入正式运行还需和论文命题、预计成本一起决定。

本次只修正了 `scienceworld_retrieval_audit.py` 的 split 核验，使 train/dev/test 套件分别查对应官方 split；检索器、Skill 库和 Agent 没有改。三种 split 的替身环境测试通过。直接启动本机 ScienceWorld Java 网关时卡住，已中止，没有生成新的离线审计文件，也没有调用 DeepSeek；本记录使用此前保存的 16 条 episode。
