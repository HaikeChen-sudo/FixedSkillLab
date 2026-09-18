# ScienceWorld 固定 Skill 主线证据审计

审计日期：2026-09-18。范围是本仓库的 ScienceWorld v6、v10、v11b、v12、v13 与 v13b；T 型 Skill 的 T1–T3 已另行结项，不并入主线效应估计。本审计只读取现有协议、代码和冻结轨迹，没有调用模型或运行新 episode。

## 结论

目前可以报告一个有范围限制的结果：在六类固定 ScienceWorld 任务、`deepseek-v4-flash`、`easy` 简化模式和 400 环境步预算下，加载经正文索引选出的固定 Skill，平均成功率和平均 Token 开销优于 No Skill。v10 与 v11b 使用未在此前 API 实验中出现的 task-variation 对；v11b 提供最清楚的单批支持。这里的“确认”指相对先前实验未使用的 variation，**不指新的任务类型、新模型或新环境**。

现有数据不能证明“正文索引一定优于只索引名称与描述”。v11b 中 Body-aware 比 Flat 多成功 3/54 次，但任务簇 Bootstrap 区间下界为 0；v10 两者同为 34/36 次成功。也不能把 Router 的效果直接归因于命中人工 Gold Skill：v11b 的三道 `boil` 题中，Body-aware 均未检出 Gold Skill，却全部成功。

v13b 的内容消融支持另一个较窄的判断：在研究者事后选出的 `boil`、`freeze` 六道题上，完整 Skill 正文优于只给元数据或等空格分词数的通用正文。实验同时改变了 Procedure 和 Termination Condition，没有单独识别 Procedure 字段的效应；六道题均复用 v11b variation，不能算新的独立留出确认。

## 证据来源与独立性

| 实验 | 设计与数据 | 与先前任务的关系 | 本审计的定位 |
|---|---|---|---|
| v6 Router | 12 题 × 5 条件 × 3 次；180 条 | 题目在该轮前固定，但研究者随后依据本轮结果继续设计确认实验 | 主线发现批次 |
| v10 确认 | 12 题 × 3 条件 × 3 次；108 条 | 与 v6 不重叠；六类任务各取第 5、6 个 test variation | 独立题目确认，单批区间触及 0 |
| v11b 平衡确认 | 18 题 × 3 条件 × 3 次；162 条 | 与 v6、v10 不重叠；六类任务各取三个未用 test variation | 当前最强的单批确认 |
| v12、v13 Pilot | 各 6 题 × 4 条件 × 1 次 | 复用 v11b 中每类一道题，并据此选择后续条件与任务类型 | 机制开发，不能计作独立复现 |
| v13b 内容消融 | 6 题 × 3 条件 × 3 次；54 条 | 复用 v11b 的 `boil:v027–v029`、`freeze:v027–v029`；v13 Pilot 后选定任务类型 | 定向内容对照，不能估计六类任务总体效应 |

v10 协议在提交 `e91bbdf` 后才开始 API 运行；v11b 替代协议在提交 `9c3e644` 后运行；v13b 协议在提交 `07e3ef6` 后运行。冻结结果分别于其后提交。v11 原定的 30 题中有 6 个 variation 不属于已安装 ScienceWorld 的官方 test split，研究者在调用 API 前废止该协议，并用 v11b 替代；[废止记录](../../results/scienceworld_v11_large_confirmation_manifest.json)保留了原因。提交顺序和轨迹时间支持“先固定协议、后评估”的过程判断，但不能证明研究者此前从未见过同一任务模板。

## 六项核心指标复核

下表由冻结 JSONL 逐条重新计算；Token、延迟均为每个 episode 的平均值。成本为该条件全部 episode 的 API 成本之和除以成功 episode 数。`Total = Input + Output` 在全部四批 504 条轨迹上逐条成立。

| 批次与条件 | 成功率 | Input Tokens | Output Tokens | Total Tokens | 延迟，秒 | 每次成功成本，USD |
|---|---:|---:|---:|---:|---:|---:|
| v6 No Skill | 25/36，69.44% | 740,335 | 3,557 | 743,891 | 73.83 | 0.007158 |
| v6 Body-aware | 32/36，88.89% | 241,813 | 2,273 | 244,086 | 40.45 | 0.002713 |
| v10 No Skill | 29/36，80.56% | 460,745 | 2,209 | 462,953 | 77.43 | 0.004256 |
| v10 Body-aware | 34/36，94.44% | 280,219 | 1,761 | 281,980 | 50.08 | 0.002551 |
| v11b No Skill | 42/54，77.78% | 876,950 | 3,755 | 880,705 | 88.18 | 0.007201 |
| v11b Flat | 45/54，83.33% | 427,292 | 2,172 | 429,464 | 55.52 | 0.003791 |
| v11b Body-aware | 48/54，88.89% | 292,543 | 1,919 | 294,462 | 48.01 | 0.002851 |

v10 的 Body-aware 对 No Skill 成功率差为 +13.89 个百分点，任务簇 Bootstrap 95% CI 为 [0, 33.33]；平均 Total Tokens 差的区间也跨过 0。v11b 的对应差为 +11.11 个百分点，95% CI 为 [1.85, 22.22]，平均 Total Tokens 差为 -586,243，95% CI 为 [-1,261,769, -128,184]。三次重复是同一道 variation 的重复测量，不能当成 54 道独立题。v11b 只有 4/18 道题的成功率上升，14 道持平；Token 降低发生在 11/18 道题，平均节省受到少数极长失败轨迹影响。六类任务中又有三类接近成功率天花板，跨任务类型外推仍弱。

v13b 的六项指标如下。三个条件加载同一条人工 Gold Skill，只有正文呈现方式不同。

| 条件 | 成功率 | Input Tokens | Output Tokens | Total Tokens | 延迟，秒 | 每次成功成本，USD |
|---|---:|---:|---:|---:|---:|---:|
| Full | 15/18，83.33% | 547,180 | 3,545 | 550,725 | 69.28 | 0.005627 |
| Metadata | 7/18，38.89% | 1,761,311 | 6,301 | 1,767,612 | 137.74 | 0.027852 |
| Placebo | 9/18，50.00% | 2,082,223 | 7,113 | 2,089,336 | 152.87 | 0.024332 |

Full 对 Metadata 的成功率差为 +44.44 个百分点；对 Placebo 为 +33.33 个百分点。两个任务簇 Bootstrap 区间分别为 [16.67, 72.22] 和 [11.11, 55.56]，但只有六个任务簇。任务级符号检验两项均为 `p=0.125`。Placebo 匹配的是 Python 空格分词数，并非 DeepSeek 实际输入 Token 数；它排除了“加入同等数量的任意空格分词就有同样收益”这一简单解释，不能严格排除所有长度、措辞和格式效应。

## 已核查的记录与解释边界

- [v6](../../results/formal_scienceworld_v6/manifest.json)、[v10](../../results/formal_scienceworld_v10/manifest.json)、[v11b](../../results/formal_scienceworld_v11/manifest.json)、[v13b](../../results/formal_scienceworld_v13b/manifest.json)四份冻结轨迹的 SHA-256 均与各自 manifest 一致；四批分别有 180、108、162、54 个唯一的 `(task, variation, repeat, condition)` 键，无缺项或多项。
- 四批记录的模型均为 `deepseek-v4-flash`，temperature 为 0，Agent 协议均标为 `scienceworld-v2`，最大环境步均为 400。每条记录的 `success` 与环境分数 ≥100 一致，模型没有自评成功。v6、v10、v11b 的 v3 Skill 哈希一致；No Skill 条件没有加载 Skill。
- v11b 的[离线检索审计](../../results/scienceworld_v11b_retrieval_audit.jsonl)调用了已安装环境的 `get_variations_test()`，18 题通过 test split 检查；[Gold 路径验收](../../results/scienceworld_v11b_gold_validation.jsonl)全部达到 100 分。这验证任务可解与分割归属，不证明 Agent 一定能解。
- [v13b 协议](../../results/scienceworld_v13b_oracle_mechanism_manifest.json)在 API 评估前固定；轨迹确认三个条件对同一道题加载相同的 Gold Skill 名称。Full 与 Placebo 保留元数据与章节结构，但同时替换 Procedure 和 Termination Condition。审计没有验证 DeepSeek 服务端在各日期是否始终使用同一底层权重；相同模型请求名不能保证这一点。

## 对外表述与下一步

可以写：“在预先固定的六类 ScienceWorld test variation 上，Body-aware 固定 Skill 检索相对 No Skill 呈现可重复的平均收益；v11b 的任务簇分析支持成功率和平均 Token 的改善。完整 Skill 正文在事后选定的状态转换题上优于两种内容对照。”不要写“Body-aware 索引机制已证明优于 Flat”，也不要写“Procedure 单独导致改善”或“Skill 普遍有效”。

先停止在这六类旧题上调 Skill、反复确认。当前已安装版本中，`boil`、`melt`、`freeze` 的官方 test variation 到 29 为止；v11b 已用完这三类尚未使用的 test variation。下一次真正独立的任务确认，需要先选新的任务类型或新环境，并在看 API 结果前冻结题目、Skill、比较条件和分析规则。复用旧题换模型可以检验跨模型稳健性，但不能补充“新题留出”证据。
