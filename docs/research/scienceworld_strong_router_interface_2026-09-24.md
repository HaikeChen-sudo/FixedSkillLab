# ScienceWorld 强基线路由接口检查

日期：2026-09-24。范围：代码接入与本地检查，没有新增付费实验，也没有新的任务成功率。

## 接入了什么

现有 Agent 新增四个独立条件，不改变旧条件的含义与默认设置。

| 条件名 | 检索方法 | 索引内容 |
|---|---|---|
| `bm25_flat_retrieval` | BM25 | Name、Description |
| `bm25_body_retrieval` | BM25 | 完整 Skill |
| `semantic_flat_retrieval` | 本地 MiniLM | Name、Description |
| `semantic_body_retrieval` | 本地 MiniLM | 完整 Skill |

四组均取 Top-3，按检索顺序加载三条完整 Skill。Flat 只是索引字段较少，并不是只给 Agent 看元数据。Gold 标签只用于记录命中名次，不参与排序，也不传给语义检索进程。

原六个任务族使用冻结的 v3 库；v14 新任务族使用修正后的 v4d 库。旧 `flat_retrieval`、`body_aware_retrieval`、`oracle_v4` 等仍保留原实现和库版本。若以后对 v14 新任务族加 Oracle 对照，应使用 `oracle_v4d`，不能拿 v4b 的 `oracle_v4` 混作同库对照。

## 本地模型与失败处理

模型、参数和文本格式复用 [上一轮离线对照](scienceworld_retrieval_baselines_2026-09-24.md)。没有增加依赖、下载模型、调整 Skill 或改变 K。

这台设备的 ScienceWorld 与语义模型在不同虚拟环境里。Agent 仍用 `.venv/scienceworld/bin/python`，语义检索通过本地子进程调用 `.venv/retrieval/bin/python` 和 `.models/all-MiniLM-L6-v2`。路径相对于项目，不依赖终端当前目录。BM25 直接在 Agent 进程中计算。

本版每个语义检索请求冷启动一次本地模型，不做跨 episode 缓存。这样不用引入常驻服务，但会增加启动耗时。后续若改成常驻或预热模式，需要另记实现版本，不能把两种延迟混为一组。

代码核对离线审计保存的 Skill 库哈希；语义检索还核对模型文件、依赖版本、维度和长度设置。缺文件、版本不同、查询为空、输入超过 256 token、子进程失败或超时均停止，不下载、不截断、不退回哈希检索。检索失败发生在 DeepSeek 客户端创建之前。

## 记录边界

新增 `routing_ms` 与 `retrieval_metadata`。前者包含选择 Skill 的耗时；语义组包含子进程启动、模型加载、指纹校验、编码及排序。后者保存检索器身份、索引模式、Top-K、查询与索引文本哈希、Skill 库版本，以及语义模型指纹和分词长度。

原 `latency_ms` 也包含路由过程，沿用原有计时范围：从环境对象创建之后开始，包含任务加载、重置、路由和 Agent 循环，不含环境对象创建与最后关闭。实验运行器另有 `runner_ms`，包含整个 episode 调用。后续端到端延迟比较必须说明使用哪一个，不能把 `routing_ms` 再加到已有 `latency_ms` 上。

六项主指标仍分别记录：Task Success Rate、Input Tokens、Output Tokens、Total Tokens、End-to-End Latency、Cost per Successful Task。这里的输入/输出 token 和费用沿用 DeepSeek 用量；本地编码器的 token 单列，不混入 API 用量。费用是 API 费用，不包括本地 CPU 的折算成本。

本轮没有真实 episode，因此这些主指标没有新增数值。测试替身中的分数、用量和时间只用于检查字段，未写入实验日志。

## 已完成的检查

- 原有 ScienceWorld、检索审计、哈希审计及 v14c/v14d 等 54 项回归测试通过。
- 新增 8 项接口测试通过。其中 BM25 在全部 61 个保存单元的 Flat/Body 两种模式下，122 次 Top-3 均与离线结果一致。
- 实际从 ScienceWorld 的 Python 环境调用独立 MiniLM 环境，检查 `boil:v029` 和斜面 `v086` 的 Flat/Body，共 4 次本地调用。Top-3 名称及顺序与离线结果一致，分数误差在 `2e-6` 内。
- 用环境与模型客户端替身检查完整 Skill 加载、Gold 不进入检索输入、路由耗时计入总耗时、失败先于 API 客户端创建。没有启动 Java 或访问 DeepSeek。

上述检查证明接口能接通并保留离线排名，不证明新路由已经提高任务成功率。

复现全部检查，不需要 API Key，不运行真实环境：

```bash
SCIENCEWORLD_LOCAL_RETRIEVAL_TESTS=1 .venv/scienceworld/bin/python -m unittest \
  test_scienceworld_strong_retrieval test_scienceworld \
  test_scienceworld_retrieval_audit test_scienceworld_retrieval_baselines \
  test_scienceworld_hash_audit test_scienceworld_v14c test_scienceworld_v14d -q
```

不设置 `SCIENCEWORLD_LOCAL_RETRIEVAL_TESTS=1` 时，跳过真实本地模型调用，其他测试可直接用标准 Python 运行。

## 下一步的最小付费检查（尚未执行）

只复用已经见过的斜面 `v086`，比较 No Skill、语义 Flat、语义 Body，各一次，共 3 个 episode。沿用原有 `max_steps=100`、相同模型与温度，采用新的 run ID 和独立结果文件。目的仅是检查真实环境、API 与新路由串联后的轨迹和记录，不用于泛化结论，也不按单题输赢挑选方法。

不要先扩到数百个 episode。这 3 条的加载文本、停止原因和六项指标核对完毕后，再决定是否冻结未见任务的确认协议。BM25 接口已经可用，本次最小付费检查先不增加这一组。
