# ScienceWorld 检索对照：BM25 与语义向量消除了当前样本的 Top-3 命中差距

日期：2026-09-24。本文是已见题目的离线检索诊断，不是新的 Agent 实验或留出确认。

## 结论

换用 BM25 或本地预训练模型 `all-MiniLM-L6-v2` 后，Flat 和 Body-aware 在五个历史 Skill 库各自的已保存查询上都达到 Gold Hit@3 全命中。旧 v3 库的 Flat 从哈希检索的 32/48，变为这两种基线下的 48/48；Body 也都是 48/48。上一轮完整词频对照未能消除的 Flat 漏检，在本轮得到消除。

因此，现有数据不足以支持“必须索引 Skill 正文才能找到正确 Skill”。这个判断只针对当前候选库、查询和 Top-3 设置，不代表正文索引没有价值，也不代表 Flat 的 Agent 已经成功。历史在线成绩不改，但解释必须加上检索基线较弱这一限制。

Body 仍有排序优势。v3 的语义检索中，Gold 排第一的比例为 Flat 40/48、Body 47/48；两者 Top-3 全命中。排序、另外两条 Skill 的选择和加载后的执行效果是不同问题，不能用其中一项代替另外两项。

## 1. 数据与比较范围

本轮直接使用上一轮审计导出的 [source_records.jsonl](../../results/scienceworld_hash_audit_2026-09-24/source_records.jsonl)，SHA-256 为 `9fa352ecb67aae89de4a0e979ffe639d4349187983c3cdb2d53e3cd89098635d`。没有读取新 variation，也没有启动 ScienceWorld 或调用 DeepSeek。

304 条源记录全部通过原检索排名与 Skill 库哈希核验。按“任务 ID、库版本/哈希、完整查询”合并重复运行和实验条件后，得到 61 个分析单元，涉及 57 个任务 ID。它们对应 49 个“库版本 × 查询原文”组合；跨版本再合并后只有 43 种查询原文。61 不是新增 episode 数，也不是 61 个独立语言问题。

| Skill 库 | 分析单元 | 库内不同查询原文 | 候选 Skill 数 |
|---|---:|---:|---:|
| v3 | 48 | 36 | 6 |
| v4 | 4 | 4 | 10 |
| v4b | 4 | 4 | 10 |
| v4c | 4 | 4 | 10 |
| v4d | 1 | 1 | 10 |

各库单独报告，不把不同版本合并成总体命中率。v4 和 v4b 是同一组四个任务 ID；v4c 的斜面 `v085` 仍沿用历史 Gold 名称，而对应旧 Skill 的适用范围已知有误。命中这个标签不证明 Skill 内容正确。

## 2. 固定方法

所有方法使用相同的保存题面、候选集合和 Gold 标签。Flat 索引 Name、Description；Body 索引完整 Skill，包含 Activation、Procedure、Termination。索引方式不改变保存的 Skill 文本，也不表示 Agent 只加载元数据。本轮没有 Agent 加载过程。

| 方法 | 本轮设置 | 作用 |
|---|---|---|
| Hash 256 | 原有小写词与相邻二元组、有符号 256 维哈希、余弦相似度 | 重现旧路由 |
| 完整词频 | 相同词与二元组，不压缩，余弦相似度 | 排除哈希碰撞 |
| BM25 | `k1=1.5`，`b=0.75`；小写正则词；重复查询词重复计分；无词干化 | 增加词法检索对照 |
| MiniLM | 已安装的 `all-MiniLM-L6-v2`；384 维；归一化向量点积 | 增加预训练语义对照 |

BM25 参数与计分约定沿用项目已有 ALFWorld 实现。每个“库版本 × 索引模式”单独统计文档频率和平均文档长度，不把查询加入候选语料。IDF 为 `ln(1 + (N − df + 0.5) / (df + 0.5))`。所有方法按未舍入分数降序排序，同分按 Skill 名称升序，输出分数才保留六位小数。

语义模型复用本地 `.models/all-MiniLM-L6-v2`，没有下载、训练、微调或模型选择搜索。CPU 执行，批量大小 16，保留模型原有的 256 token 长度限制，不分块、不扩窗。查询最长 99 token，Flat 文本最长 30，Body 最长 239；全部未截断。这里的 token 是检索编码器的分词长度，不是 DeepSeek Input Tokens。

本轮开始前固定这些设置，没有根据结果再调 BM25 参数、模型、K 值或 Skill 内容。模型文件哈希、依赖版本、输入长度与代码哈希保存在随附数据中。

指标为 Gold Hit@1、Gold Hit@3 和 MRR。Hit@K 判断人工 Gold 标签是否位于前 K 名；MRR 是 Gold 名次倒数的平均值。它们都不是 Task Success Rate。

## 3. v3：两种新增基线都消除了 Top-3 差距

| 检索方法 | Flat Hit@1 | Flat Hit@3 | Flat MRR | Body Hit@1 | Body Hit@3 | Body MRR |
|---|---:|---:|---:|---:|---:|---:|
| Hash 256 | 16/48 | 32/48 | 0.5243 | 22/48 | 39/48 | 0.6295 |
| 完整词频 | 16/48 | 32/48 | 0.5667 | 10/48 | 48/48 | 0.5833 |
| BM25 | 26/48 | 48/48 | 0.7153 | 40/48 | 48/48 | 0.8889 |
| MiniLM | 40/48 | 48/48 | 0.9167 | 47/48 | 48/48 | 0.9896 |

进一步按查询原文与 Gold 标签合并后，v3 有 36 个单元。BM25 和 MiniLM 的 Flat、Body Hit@3 仍全为 36/36。MiniLM Hit@1 为 Flat 28/36、Body 35/36，说明这一排序差异不只来自 variation 重复计数。不过，这些查询仍来自已见材料，不能据此报告新的泛化显著性。

Body MiniLM 唯一未排第一的是 `find-non-living-thing:v229`：`find-living-object` 排第一，正确的 `find-nonliving-object` 排第二，分数分别为 0.546676 和 0.544110。语义编码也会混淆近义但要求相反的候选，不能把它视为 Oracle。

### 旧 v11b 主实验的查询子集

| 检索方法 | Flat Hit@3 | Body Hit@3 | Flat Hit@1 | Body Hit@1 |
|---|---:|---:|---:|---:|
| Hash 256 | 12/18 | 15/18 | 6/18 | 6/18 |
| 完整词频 | 12/18 | 18/18 | 6/18 | 3/18 |
| BM25 | 18/18 | 18/18 | 9/18 | 15/18 |
| MiniLM | 18/18 | 18/18 | 15/18 | 18/18 |

这张表只重算 v11b 的 18 个任务查询，不是新增 18 个执行结果，也不是把历史的三次重复重新算作独立检索样本。旧 v11b 中 Body、Flat 的成功率和成本差异仍是原实现下的观测；不能将其归纳为正文索引相对强 Flat 基线的优势。

## 4. v4 系列与斜面单题

| Skill 库 | BM25 Flat Hit@1 / Hit@3 | BM25 Body Hit@1 / Hit@3 | MiniLM Flat Hit@1 / Hit@3 | MiniLM Body Hit@1 / Hit@3 |
|---|---|---|---|---|
| v4，4 个单元 | 3/4；4/4 | 4/4；4/4 | 4/4；4/4 | 4/4；4/4 |
| v4b，4 个单元 | 3/4；4/4 | 4/4；4/4 | 4/4；4/4 | 4/4；4/4 |
| v4c，4 个单元 | 4/4；4/4 | 4/4；4/4 | 4/4；4/4 | 4/4；4/4 |
| v4d，1 个单元 | 1/1；1/1 | 1/1；1/1 | 1/1；1/1 | 1/1；1/1 |

对最新斜面 `inclined-plane-determine-angle:v086`，Flat 的 Gold 名次依次为 Hash 256 第 5、完整词频第 1、BM25 第 1、MiniLM 第 1。旧 Flat 在线失败不能单独用来论证需要 Body-aware；强 Flat 检索能在离线阶段找到 Gold。

但找到 Gold 不等于执行成功。原在线结果仍为 No Skill、Body、Oracle 成功，Flat 失败；本轮没有补出任何新的 Agent 成败标签。

## 5. 全命中仍不等于加载内容相同

在 v3 的 48 个分析单元中，BM25 的 Flat 与 Body 只有 1 个单元的 Top-3 集合完全相同；MiniLM 有 19 个集合相同，只有 12 个连顺序也相同。即使 Gold 都已进入 Top-3，另外两条 Skill 和位置仍经常变化。

因此，当前材料只能回答“是否检索到 Gold”，不能直接回答“哪组加载内容更有利于执行”。如果之后发现在线差异，候选干扰与位置是需要检查的解释，不能自动归因于 Gold 覆盖率。也不能仅因本轮 Hit@1 有差异，就把原定 Top-3 换成 Top-1 后继续声称确认原假设。

## 6. 对研究主线的判断

我不建议继续围绕原来的 256 维排名改 Skill，或直接把当前 Body-aware 路由包装成方法贡献。新对照说明，原有 Flat 的漏检可以被已有的词法方法和预训练模型消除。这削弱了“正文索引提升 Gold Top-3 覆盖”的论证，不会抹去此前固定 Skill 内容对执行可能有用的证据；内容有效、路由有效和结构有效必须分开判断。

本轮也不能否定所有正文索引方案。Body 在当前语义模型下仍更常把 Gold 排第一，但候选库很小：v3 的 Top-3 已占 6 条候选的一半，存在明显的指标饱和。这里没有新算法，也没有原创性结论。

若继续付费实验，下一步应先冻结强基线路由的实现与协议，做少量已见题的接口检查，再决定是否用尚未检查的任务做配对确认。保持模型、Skill 库、任务、预算和 K 一致，比较语义 Flat 与语义 Body，保留 No Skill 对照。已有 61 个分析单元只能用作开发材料。没有执行数据前，不预设 Body 会赢。

本轮六项在线主指标均不适用：Task Success Rate、Input Tokens、Output Tokens、Total Tokens、End-to-End Latency、Cost per Successful Task。没有新增 episode，不能把离线命中率或编码器长度填进这些指标；也没有测量在线路由延迟或重新估算旧费用。

## 7. 核验与复现

结果文件：

- [逐题完整排名与来源行号](../../results/scienceworld_retrieval_baselines_2026-09-24/rankings.jsonl)
- [各库、去重查询、各历史 run 的汇总与模型指纹](../../results/scienceworld_retrieval_baselines_2026-09-24/summary.json)
- [全部编码输入的长度与截断检查](../../results/scienceworld_retrieval_baselines_2026-09-24/embedding_inputs.jsonl)

验证包括：7 项单元/回归测试；244 组 Hash/完整词频排名与上轮审计一致；用独立 BM25 算式及直接 Transformer 输出的遮罩均值池化重算 244 组新增基线完整排名，顺序全部一致，输出分数的最大绝对差约为 `5.93e-7`。汇总另从完整排名中的 Gold 位置重算，分母与结果一致。

同一脚本另写入临时目录完整重跑，三份输出文件逐字节一致。模型运行时固定为本地离线模式；没有访问 API、改生产检索器或覆盖历史数据。

```bash
python3 -m unittest test_scienceworld_retrieval_baselines test_scienceworld_hash_audit -q

.venv/retrieval/bin/python scienceworld_retrieval_baselines.py \
  results/scienceworld_hash_audit_2026-09-24/source_records.jsonl \
  --model-dir .models/all-MiniLM-L6-v2 \
  --output-dir results/scienceworld_retrieval_baselines_replay
```

输出目录必须尚不存在。脚本拒绝覆盖已有结果；本地模型缺文件时直接停止，不自动下载。换机器复现时，应核对 `summary.json` 中的模型文件与依赖版本。新的模型设置应另建对照，不覆盖本轮记录。
