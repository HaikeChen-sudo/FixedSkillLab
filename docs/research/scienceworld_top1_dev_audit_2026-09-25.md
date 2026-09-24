# ScienceWorld：Semantic Top-1 开发集可行性检查

日期：2026-09-25。性质：回顾性离线检查，不是新的 Agent 实验。

## 决定

暂不启动 Top-1 付费对比。现有离线排名中符合官方开发集划分的 13 个任务／库版本记录，Semantic Flat 与 Semantic Body 的第一名均相同，并均命中 Gold。若两组只加载该第一名的完整 Skill，则输入的 Skill 文本相同；重复运行产生的轨迹差异不能归因于正文检索。

这不证明 Body 索引在其他任务上无效。它说明这批开发数据不能支持我们提出的 Top-1 区分实验。

## 数据范围与结果

使用已保存的 `results/scienceworld_retrieval_baselines_2026-09-24/rankings.jsonl`。先校验原清单中的文件哈希，再按本地 ScienceWorld 官方划分筛选；没有新增查询文本、重算向量或调用 DeepSeek。

原缓存有 61 个任务／库版本／查询文本记录，其中 48 个属于官方测试集，全部排除。保留 13 个开发集记录，涉及 9 个不同任务实例、4 个任务家族。该缓存没有合格的训练集记录。范围仅限这份历史缓存，不代表项目所有已见 train/dev 查询；本次未补算新预算 Pilot 的排名。

| 冻结 Skill 库版本 | 任务／查询记录 | 库内去重查询＋Gold | Flat 命中@1 | Body 命中@1 | 第一名不同 |
| --- | ---: | ---: | ---: | ---: | ---: |
| v4 | 4 | 4 | 4/4 | 4/4 | 0 |
| v4b | 4 | 4 | 4/4 | 4/4 | 0 |
| v4c | 4 | 4 | 4/4 | 4/4 | 0 |
| v4d | 1 | 1 | 1/1 | 1/1 | 0 |

v4 与 v4b 重用了相同的 4 个任务实例，不能把跨版本记录合并成 13 道独立题。每个版本内的“仅 Flat 命中”“仅 Body 命中”“均未命中”计数都是 0。Gold 只用于离线判定，未加入检索查询。

## 核验与限制

官方划分来自 ScienceWorld 的 `get_variations_train/dev/test`，通过各家族的 train v000 读取元数据；没有执行任务动作、读取新的测试任务内容或生成 Gold 路径。划分快照保存了包版本与 JAR 哈希。原 MiniLM 输入审计无截断，原完整排名保留了未取整分数排序后的顺序。本次直接取保存的第一名，不按显示用的取整分数重新排序。

脚本校验查询和 Skill 库哈希、候选集合、排名连续性、Gold 排名与官方划分。5 项单元测试覆盖测试集误标排除、重复记录、四种命中组合、哈希／划分错误和 Gold 排名不一致。

六项 Agent 指标本轮均未测量：Task Success Rate、Input Tokens、Output Tokens、Total Tokens、End-to-End Latency、Cost per Successful Task。检索命中率 100% 不等于任务成功率 100%。

## 下一步边界

先归档此次零差异结果，不增加付费 episode，也不修改 Skill 来人为制造分歧。当前开发集以任务名称明确的四个家族为主，覆盖范围有限。

若继续研究正文索引，应先用任务定义预先选择一批新的官方 train/dev 查询，冻结候选库、编码器和统一加载方式，在不查看 Agent 成败的条件下做离线筛查。筛查中若没有分歧，就停止这项比较；若存在分歧，再制定小规模配对实验。不能从旧测试集里挑出 Body 获胜的题来充当新的确认集。

## 复现与文件

在项目目录执行；输出必须使用新路径，脚本拒绝覆盖已有结果。

```sh
python3 scienceworld_top1_audit.py --splits results/scienceworld_top1_splits_2026-09-25.json --output /tmp/scienceworld_top1_dev_audit_recheck.json
python3 -m unittest test_scienceworld_top1_audit -v
```

重新读取官方划分时需使用 ScienceWorld 虚拟环境，并给两个输出指定尚不存在的路径：

```sh
.venv/scienceworld/bin/python scienceworld_top1_audit.py --collect-splits --splits /tmp/scienceworld_top1_splits_recheck.json --output /tmp/scienceworld_top1_audit_live_recheck.json
```

- 代码：`scienceworld_top1_audit.py`。
- 单元测试：`test_scienceworld_top1_audit.py`。
- 官方划分快照：`results/scienceworld_top1_splits_2026-09-25.json`。
- 逐条结果与汇总：`results/scienceworld_top1_dev_audit_2026-09-25.json`。
- 原缓存 SHA-256：`8746e43b4f853c8bca29e8f880503ef8ad105dd109133b2a52b155fb796621f6`。

在线 Agent、历史 Skill 库、预算协议及已有实验结果均未修改。
