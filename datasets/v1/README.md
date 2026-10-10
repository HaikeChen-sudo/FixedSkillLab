# FixedSkillLab Dataset v1

固定 Skill 的 Agent 执行与成本数据库（正式发布包 1.0.0），**指标版（metrics-only）**。包含七批实验的 984 条已保存运行记录，保留成功与失败。它不是新 benchmark，也不是可直接微调的对话训练集。

完整下载包位于仓库的 `datasets/fixedskilllab-metrics-1.0.0.zip`，解压后即可独立使用。1.0.0 是不可变发布标识，不表示还需要追加实验才能使用。\n\nPython 3.9+ 即可使用。无需 API Key、GPU、模型下载、ALFWorld 或 ScienceWorld 安装；也无需安装 pandas。

## 能用来做什么

- 按批次比较不同 Skill 条件的成功率、Token、耗时与估算费用。
- 找到同题重复运行中的退步、改善与高成本样本，核对平均值是否被少量长运行主导。
- 在记录了 Skill 提示指纹的批次中，区分加载相同内容和不同内容的配对。
- 验证自己的实验统计、缺失值处理与结果可视化代码。

本版不含任务指令、环境观察、动作文本、模型回复、Skill 正文或逐步 Token。因此不能仅凭这个包分析具体失败动作、训练执行策略、重放环境，或证明失败原因。原始轨迹存在于历史来源文件中，不等于这些文字已纳入本次发布与许可范围。

## 直接查询数据库

下载 [fixedskilllab.sqlite](fixedskilllab.sqlite)，用支持 SQLite 的工具打开即可查询。数据库没有服务端、账号或安装脚本。授权说明请同时保留 LICENSE 与 THIRD_PARTY.md。

数据库包含五张表与一个汇总视图：

| 对象 | 主键与用途 |
| --- | --- |
| episodes | episode_id；另有批次／任务／条件／重复的联合唯一约束，保存逐次运行指标 |
| batches | batch_id；七批来源、范围与指纹 |
| loaded_skills | episode_id + position；逐次 Skill 名称与加载顺序，外键关联 episodes |
| data_dictionary | table_name + column_name；字段类型、空值规则和定义 |
| release_metadata | key；发布版本、来源提交与构建 SQLite 版本 |
| condition_metrics | 汇总视图；按批次与条件计算全部六项指标 |

数据库有主键、外键、非负数与 Token 加总约束，并为任务、条件和 Skill 名称建立索引。日期保留 ISO 字符串，success 用 0/1，未知值用 SQL NULL。Skill 名称不存在某行表示该 episode 的加载列表为空，不是丢失占位行。

SQL 示例：

```sql
SELECT * FROM condition_metrics
WHERE batch_id = 'scienceworld_v11b';

SELECT batch_id, task_id, condition, repeat, total_tokens, cost_usd
FROM episodes WHERE success = 0
ORDER BY total_tokens DESC LIMIT 20;
```

[queries.sql](queries.sql) 还提供逐题配对、缺失检查、加载顺序和字段字典查询。配对查询限定批次、任务与重复编号，不能只按任务名连接。

也可仅用 Python 标准库打开数据库；以下方式不会意外创建新文件：

```python
import sqlite3
from pathlib import Path

path = Path("datasets/v1/fixedskilllab.sqlite").resolve()
with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
    for row in db.execute("SELECT * FROM condition_metrics WHERE batch_id=?", ("scienceworld_v11b",)):
        print(row)
```

## 两分钟开始

在仓库根目录执行：

```sh
python3 datasets/v1/use_dataset.py --check
python3 datasets/v1/use_dataset.py --batch scienceworld_v11b
python3 datasets/v1/use_dataset.py --batch semantic_top3 --compare semantic_flat_retrieval semantic_body_retrieval
```

第一条验证包内哈希、字段、主键、批次覆盖与指标一致性，应显示 984 条记录、7 批、77 次失败和 `checks: passed`。第二条输出同一批次的完整六项指标。第三条输出逐题配对，差值方向为 **右组减左组**；`same_skill_prompt: null` 表示无法判断，不能当作“相同”。未找到一方或覆盖不齐会报错，不会悄悄只比较交集。

只下载此文件夹也可使用：在文件夹内运行 `python3 use_dataset.py --check`。保留文件夹内所有文件，尤其是 LICENSE、THIRD_PARTY.md 与 checksums.json。

直接读取：

```python
import json
from pathlib import Path

rows = [json.loads(line) for line in Path("datasets/v1/episodes.jsonl").read_text(encoding="utf-8").splitlines()]
selected = [r for r in rows if r["batch_id"] == "scienceworld_v11b"]
print(len(selected))  # 162
```

可选的 [quickstart.ipynb](quickstart.ipynb) 使用相同的标准库检查与分析函数。Jupyter 不是命令行示例的依赖。

## 文件

| 文件 | 内容 |
| --- | --- |
| [fixedskilllab.sqlite](fixedskilllab.sqlite) | 可直接查询的 SQLite 数据库，五表、一视图，内置字段字典 |\n| [episodes.jsonl](episodes.jsonl) | 主数据；每行一次已保存的 episode，共 46 个字段 |
| [episodes.csv](episodes.csv) | 同样的记录；空单元格表示 null，Skill 列是 JSON 数组，布尔值为 true/false |
| [condition_summary.csv](condition_summary.csv) | 按批次与条件汇总的 24 行结果，不跨批次混算 |
| [schema.json](schema.json) | 每个字段的类型、单位、来源和空值说明，禁止额外字段 |
| [manifest.json](manifest.json) | 来源路径、SHA-256、批次范围及构建脚本指纹 |
| [quality.json](quality.json) | 重复检查、缺失计数和已知限制，含逐批次缺失情况 |
| [checksums.json](checksums.json) | 包内发布文件的 SHA-256；不包含它本身，不是数字签名 |
| [use_dataset.py](use_dataset.py) | 独立离线校验、汇总与逐题配对 |

## 数据范围与选择方式

| batch_id | 来源批次 | 实例×条件×重复 | 记录 | 来源 split |
| --- | --- | --- | ---: | --- |
| alfworld_v5 | ALFWorld v5 | 30×5×3 | 450 | valid_unseen |
| alfworld_v8 | ALFWorld v8 | 20×3×3 | 180 | valid_seen |
| scienceworld_v11b | ScienceWorld v11b | 18×3×3 | 162 | test |
| scienceworld_v13b | ScienceWorld v13b | 6×3×3 | 54 | test |
| semantic_top3 | 强语义 Top-3 | 6×3×3 | 54 | test |
| semantic_top1_dev | 语义 Top-1 开发诊断 | 4×3×3 | 36 | dev |
| content_dev | 固定内容开发对照 | 4×4×3 | 48 | dev |

这七批沿用技术报告的已有范围，不按单条成败筛选。收集时间按源记录为 2026-09-03 至 2026-10-08；准备日期为 2026-10-10。共 907 次成功、77 次失败，覆盖 82 个不同的 `(environment, task_id)` 标识。**这些数值只描述覆盖范围，不把 984 条记录或 82 个标识当作独立同分布样本。** 本包不是仓库全部历史实验，也不包含未保存为完整 episode 的中断尝试。

所有记录请求的模型别名均为 `deepseek-v4-flash`，temperature 为 0；没有保存提供商后台权重快照。模型、题目选择、预算、Skill 库和工具协议的限制需要一起阅读。`source_split` 忠实记录原环境标签，未重新认证为从未查看过的盲测集，也不提供新的训练／验证／测试划分。

主键为 `(batch_id, task_id, condition, repeat)`。不同批次的同名条件不一定是同一个方法；task_id 也不能证明跨批次初始状态完全一致。若用于成本预测，应按任务或任务族分组切分并防止跨批次重叠泄漏，不能随机拆 episode 后声称对新任务泛化。成败、调用数和总 Token 都是运行后信息，不能当作运行前成本预测的输入。

## 六项指标

| 指标 | 计算与限制 |
| --- | --- |
| Task Success Rate | 成功完成记录数／该组已保存记录数。输出 successes 与 episodes；不等于所有 API 尝试的成功率 |
| Input Tokens | episode 内全部请求累计输入，再按条件求均值；含重复发送的上下文 |
| Output Tokens | episode 内累计输出，再求均值 |
| Total Tokens | Input + Output；不等于单次上下文长度、FLOPs、GPU 时间或能耗 |
| End-to-End Latency | 仅使用原 `runner_ms`。无记录则 null；另列 `legacy_latency_ms`，禁止混用补齐 |
| Cost per Successful Task | 全组估算费用之和／成功数，包括失败 episode 的费用；零成功或任一费用缺失则 null |

费用保留历史计价与缓存估算，不按今天的价格重算，也未与账单核对。路由与初始化是否包含在旧计时中受版本影响。`runner_ms` 只代表单次 runner 包围的执行区间，不包括整次命令启动和未落盘重试的所有开销。

主要缺口：846/984 条缺 `runner_ms`，900/984 条缺初始观察哈希。完整的提供商模型快照与环境软件指纹未纳入本包。其他缺失见 quality.json：null 可能是未记录或不适用（例如 No Skill 的检索器），不能统一替换为零。

## 复核与可追溯性

每条记录都有 `source_file`、`source_line`、文件 SHA-256 与原行 SHA-256。来源文件是仓库内已跟踪的快照，不会在导出时修改。来源基准提交为 `95d2e24`；它是归档定位，不代表每次实验的执行代码提交。

在完整仓库中复核导出：

```sh
python3 build_dataset.py --check
python3 -m unittest test_dataset -v
```

构建到新目录：

```sh
python3 build_dataset.py --build --output /tmp/fixedskilllab-dataset-v1 --archive /tmp/fixedskilllab-metrics-1.0.0.zip
```

构建器固定七个来源哈希，只投影允许的字段，不调用现有 Agent、不推断缺失预算、不从当前 Skill 库重建历史提示。若已有文件内容不同，会拒绝覆盖，请换一个新目录。SQLite 构建版本记录在 release_metadata；不同 SQLite 版本可能产生不同二进制布局，跨平台再导出时应使用新目录并比对逻辑记录，而非擅自更新旧哈希。包内自检同时检查 SQLite 完整性、外键及其与 JSONL 的逐字段一致性；完整仓库的构建检查才核对来源。两者都不是线上环境重跑，也不证明因果效果。

旧批次可能用于后续开发；没有发布“所有方法的总体排名”。报告均值时保留失败与长运行，并同时检查逐题差额；重复运行应配对，三次运行标准差不是任务总体的不确定性。

## 许可与引用

项目原创整理材料与指标集合沿用仓库 [MIT LICENSE](LICENSE)，不为第三方资产授予新许可。软件许可来源、未纳入内容和再利用边界见 [THIRD_PARTY.md](THIRD_PARTY.md)。这份小型指标发布包与包含历史原文的整个仓库并非同一个授权对象。

引用时写明作者 Haike Chen、名称 FixedSkillLab Dataset v1 (metrics-only)、版本 1.0.0、仓库地址和实际使用的提交或 manifest 哈希。不虚构 DOI。研究使用 ALFWorld 或 ScienceWorld 时，也应引用对应环境论文。

English summary: 984 saved agent episodes from seven heterogeneous experiment batches. This metrics-only release retains successes, failures, token usage, historical cost estimates, timing availability and recorded Skill fingerprints. No raw environment text, model responses or Skill bodies are included. Use within-batch paired comparisons; repeated episodes are not independent tasks. Python standard library only. See schema.json and quality.json before analysis.


