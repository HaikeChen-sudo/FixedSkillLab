# FixedSkillLab 主张—证据表

2026-10-09。配套[论文提纲](fixedskilllab_paper_outline_2026-10-09.md)。这是写作依据与限制清单，不是新实验，不改变任何历史判据。

## 主张清单

“可写”表示在限定范围内有对应记录，不表示结果新颖、存在普遍因果效应或满足投稿要求。

| 编号与拟写主张 | 直接观察 | 判断与禁止外推 | 证据入口 |
| --- | --- | --- | --- |
| C1：固定指导的收益在本项目各批次中并不一致。 | ScienceWorld v11b：No Skill 42/54、Body 48/54；ALFWorld v5：88/90 对 85/90；ALFWorld v8：No Skill 与 Oracle v7 均 60/60。 | 可作描述性综合。跨环境任务、库、预算、协议不同，不能将方向差异归为环境本身，也不能推出 Skill 普遍有用／无用。 | E1–E3；[跨环境审计](fixedskilllab_cross_environment_synthesis.md) |
| C2：旧 Top-3 命中差距不足以证明必须索引正文。 | 同一保存查询的 v3 库中，BM25 和 MiniLM 的 Flat／Body Hit@3 均为 48/48；旧 Hash Flat 为 32/48。 | 可写离线结果。48 个分析单元并非 48 个独立题面；这是已见查询诊断，不能把命中率当新 Agent 成功率。 | E4；[强基线审计](scienceworld_retrieval_baselines_2026-09-24.md) |
| C3：汇总 Token 优势不能直接归因于检索改变了指导。 | 强语义 Top-3 的 18 对中 12 对提示相同；Flat−Body Token 总差 269,283，同提示贡献 405,223，不同提示贡献 −135,940。 | 可写算术分解与归因限制。同提示并非完整上下文相同，也不是严格随机化安慰剂；未知波动来源不编造。 | E5；[结题复核 §5](scienceworld_content_closeout_2026-10-08.md) |
| C4：允许直接移动减少动作的假设没有通过本轮开发判据。 | 四组各成功 12/12；正确组相对必须先拾取组，0/4 实例同时减少调用和拾取命令，要求为至少 3/4。 | 可按预定规则记未复现。只有一个任务族四实例；起始房间不同，拾取不等于冗余。不能否定全部同房间直接移动场景。 | E7；[冻结判据](scienceworld_content_dev_protocol_2026-10-08.md) |

## 补充证据：保留，但不提升为独立机制贡献

| 材料 | 能保留的观察 | 不能用于什么结论 |
| --- | --- | --- |
| E6：Top-1 四题 | 两种检索均 12/12，无 Skill 9/12；提示相同与不同的配对均有 Token 差额。 | 不是新的盲测；局部少拾取现象不等于已经确认了单句机制。 |
| E8：v13b 内容消融 | Full／Metadata／Placebo 分别成功 15/18、7/18、9/18。 | 同时改变 Procedure 和 Termination，且复用 v11b 六题；不能叫 Procedure-only 因果效应或独立新题确认。 |
| E9：Procedure holdout | 斜面 P0 9/9、P1 8/9，未满足成功率不降条件；评分器对新实例出现误读。 | 旧过程评分不用于证明增益；修正评分后的分析不能倒填成预注册结果。 |
| T1–T3 | 已有[结题记录](scienceworld_t_shaped_t1_t3_closeout.md)保留组合门槛未通过的结果。 | 不把某组省 Token 改写成 T 型互补成立；不并入检索方法的总体效应。 |

## 证据登记与分析单位

| 来源编号 | 运行与单位 | 原始记录、计划与分析 |
| --- | --- | --- |
| E1 | `alfworld-v5-test-30x3`；30 实例×5 组×3 次，450 episode。 | [冻结 JSONL](../../results/formal_v5/alfworld-v5-test-30x3.jsonl)、[归档 manifest](../../results/formal_v5/manifest.json)、[汇总](../../results/formal_v5/condition_summary.csv)。归档 manifest 不冒充执行前协议。 |
| E2 | `alfworld-v8-confirm-20x3`；20 实例×3 组×3 次，180 episode。 | [冻结 JSONL](../../results/formal_v8/alfworld-v8-confirm-20x3.jsonl)、[归档 manifest](../../results/formal_v8/manifest.json)、[汇总](../../results/formal_v8/condition_summary.csv)。 |
| E3 | `scienceworld-v11b-confirm-18x3`；18 实例×3 组×3 次，162 episode。 | [冻结 JSONL](../../results/formal_scienceworld_v11/scienceworld-v11b-confirm-18x3.jsonl)、[运行前清单](../../results/scienceworld_v11b_confirmation_manifest.json)、[归档 manifest](../../results/formal_scienceworld_v11/manifest.json)、[配对统计](../../results/formal_scienceworld_v11/paired_statistics.csv)。 |
| E4 | 历史检索离线诊断；61 个“任务／库／查询”单元，v3 子集为 48。没有新 episode。 | [排名](../../results/scienceworld_retrieval_baselines_2026-09-24/rankings.jsonl)、[分析与指纹](../../results/scienceworld_retrieval_baselines_2026-09-24/summary.json)、[方法说明](scienceworld_retrieval_baselines_2026-09-24.md)。不能称为运行前登记。 |
| E5 | `scienceworld-strong-confirm-6x3`；6 实例×3 组×3 次，54 episode。 | [JSONL](../../results/scienceworld_strong_confirm_6x3.jsonl)、[运行前协议](scienceworld_strong_confirmation_2026-09-24.md)、[清单](../../results/scienceworld_strong_confirmation_manifest.json)、[复核分析](../../results/scienceworld_content_closeout_2026-10-08.json)。 |
| E6 | `scienceworld-top1-mechanism-dev-4x3`；4 实例×3 组×3 次，36 episode。 | [JSONL](../../results/scienceworld_top1_pilot.jsonl)、[协议](scienceworld_top1_pilot_protocol_2026-10-08.md)、[清单](../../results/scienceworld_top1_pilot_manifest.json)、[分析](../../results/scienceworld_top1_analysis_2026-10-08.json)。 |
| E7 | `scienceworld-content-dev-4x3`；4 实例×4 组×3 次，48 episode。 | [JSONL](../../results/scienceworld_content_dev/episodes.jsonl)、[协议](scienceworld_content_dev_protocol_2026-10-08.md)、[清单](../../results/scienceworld_content_dev/manifest.json)、[查询与初始观察哈希](../../results/scienceworld_content_dev/queries.json)、[分析](../../results/scienceworld_content_closeout_2026-10-08.json)。 |
| E8 | `scienceworld-v13b-oracle-mechanism-6x3`；6 实例×3 组×3 次，54 episode，实例复用 E3。 | [冻结 JSONL](../../results/formal_scienceworld_v13b/scienceworld-v13b-oracle-mechanism-6x3.jsonl)、[运行前清单](../../results/scienceworld_v13b_oracle_mechanism_manifest.json)、[归档 manifest](../../results/formal_scienceworld_v13b/manifest.json)、[主线审计](scienceworld_mainline_evidence_audit.md)。 |
| E9 | `scienceworld-procedure-holdout-6x3`；6 实例×2 组×3 次，36 episode。 | [协议](scienceworld_procedure_holdout_prereg_2026-09-22.md)、[清单](../../results/scienceworld_procedure_holdout_manifest.json)、[结案说明](scienceworld_procedure_holdout_closeout_2026-09-22.md)。原始记录在未纳入 Git 的本地总账 `results/scienceworld_results.jsonl`；公开复核材料尚有缺口。 |

上述行数不相加为“独立样本数”。v13b 重用 v11b，离线检索又复用多轮查询；三次重复也没有增加独立 task-variation 数。Mini Lab 仅保留为管线背景，不将全成功 Pilot 当成支持或反对通用 Skill 的正式证据。

## 六项指标的计时与费用约束

| 指标 | 所有在线主表应保留的内容 |
| --- | --- |
| Task Success Rate | 分子、分母与环境判据，失败记录保留；API 异常另记。 |
| Input Tokens | 全 episode 累计输入，不能换成提示文本长度。 |
| Output Tokens | 全 episode 累计输出，与输入分列。 |
| Total Tokens | 逐条核对 Input＋Output；不冒充实际 compute。 |
| End-to-End Latency | E5–E7 使用实际 `runner_ms`。E1–E3、E8 的完整字段未记录；完整时间列记缺失，旧 `latency_ms` 独立附列并解释边界。 |
| Cost per Successful Task | 全条件总估算费用／成功数；零成功记未定义。历史价格、缓存与未落盘调用的限制随表披露。 |

E9 的计时边界需在独立原始快照准备好后单独核验，本稿不替它补充完整时间。已发表在仓库的旧表若曾将 `latency_ms` 宽泛称为端到端，本稿使用更严格口径，不无声修改旧文件。

## 文献对照与可写程度

| 本地拟写内容 | 相关工作已有覆盖 | 本稿保留的定位 |
| --- | --- | --- |
| Skill 有收益，也可能退化 | [Agent Skills Can Be Harmful](https://arxiv.org/abs/2608.11888) | 本项目具体设置的复核，不宣称首次发现。 |
| 检索与实际使用分开 | [Skill Following](https://arxiv.org/abs/2609.00549)、[SRA-Bench](https://arxiv.org/abs/2604.24594) | 具体加载文本与逐题成本的审计记录，不声称新因果估计器。 |
| 强基线改变方法判断 | [SkillSeek](https://arxiv.org/abs/2609.38822) | 保留本项目由弱基线到强基线的证据变化，不能只换环境就称算法贡献。 |
| 流程审计或选择性加载 | [Skill-Use](https://arxiv.org/abs/2608.04828)、[SIGIL v3](https://arxiv.org/abs/2607.27309v3)、[SkillApt](https://arxiv.org/abs/2609.26863) | 不属于本稿已实现的新方法。 |

这些来源和边界已在[相关工作更新](fixed_skill_candidate_prior_art_2026-10-08.md)中核查。本次写作复用该核查，没有声称完成穷尽性综述。

## 本次核验与尚未完成的事

本次重读协议、清单和已有分析；E1、E2、E3、E8 的冻结文件哈希与各自归档 manifest 相符，成功计数与表述相符，均没有 `runner_ms`。E3、E8 的 success 字段与环境 score≥100 相符。E5–E7 复用已有离线校验和来源指纹。这里未重新估计统计区间，未运行环境，也未调用模型。

正文扩写前优先处理两项材料问题：

- E9 若作为可复核结果引用，需要从本地总账按固定 run ID 导出完整快照、验证唯一键和清单哈希，并另存来源指纹。不能拿旧失效评分器的输出当作过程收益。
- E1、E2 的执行前计划与变更时间线应补入方法附录；归档 manifest 只能证明当前文件身份，不足以单独证明先登记后运行。在此之前不把两批的全部解释称为预注册确认。

主结果 C1–C4 不依赖 E9 的失效评分器。材料缺口可以通过现有文件核对解决的，先核对；不存在的计时、隐藏状态或服务端权重记录保持缺失，不能通过一次新实验追补成历史事实。

当前允许推进的是方法与结果草稿，不是投稿声明。若写完后仍不能说明相对先例增加了什么可验证认识，应以技术报告和可复现仓库收尾；不为凑方法创新继续消耗测试集。
