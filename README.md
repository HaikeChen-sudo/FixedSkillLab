# FixedSkillLab

固定 Skill 加载与检索的 LLM Agent 实验平台。仓库包含一个只用 Python 标准库的确定性 Mini Lab，以及 ALFWorld 和 ScienceWorld 的文字交互实验。成功条件均由程序或环境判断，模型不能给自己打分。

定稿报告：[Mini Lab 阶段报告](output/pdf/Mini_Lab_阶段科研报告.pdf) · [ALFWorld v8 确认研究报告](output/pdf/ALFWorld_固定Skill研究报告_v8.pdf) · [ScienceWorld v10 发现与确认报告](output/pdf/ScienceWorld_固定Skill检索发现与确认报告_v10.pdf) · [ScienceWorld v11b 平衡确认报告](reports/scienceworld_v11b/ScienceWorld_固定Skill检索平衡确认报告_v11b.md)

## 运行

Mini Lab 需要 Python 3.9+，不安装第三方依赖。

```bash
python3 minilab.py list
python3 minilab.py show csv-02
python3 minilab.py self-check
python3 minilab.py skill-check
python3 -m unittest -v
```

交互执行一题：

```bash
python3 minilab.py play text-01
```

每行输入一个 JSON action：

```json
{"tool":"read_file","args":{"path":"inbox/code.txt"}}
{"tool":"submit","args":{"value":"7319"}}
{"grade":true}
```

`play` 默认使用临时目录。要保留现场，传入一个空目录：

```bash
mkdir run-01
python3 minilab.py play csv-02 --workspace run-01
```

## Python 接口

```python
from minilab import MiniLab

with MiniLab() as lab:
    spec = lab.reset("calc-01")
    result = lab.call_tool("calculate", expression="17 * 23")
    lab.call_tool("submit", value=result)
    print(lab.grade())
```

`reset()` 返回题目、成功条件、步数上限和工具说明。`grade()` 只读取实际文件状态或 `submit()` 保存的结构化值，不读取模型解释。

## 最小 Agent

[agent.py](agent.py) 是不使用 Skill 的 Agent 控制循环。模型直接看到 Mini Lab 的 16 个工具；它选择工具和参数，Agent 执行工具并将 JSON 结果回传。模型看不到 `success_condition`，也无法调用 `grade()`。

本地端到端 smoke test：

```bash
python3 agent.py replay calc-01
```

`replay` 复放参考 action，只验证 Agent 循环和工具协议，不是模型实验结果。

用 DeepSeek API 跑一题：

```bash
export DEEPSEEK_API_KEY='...'
python3 agent.py deepseek csv-02 --model YOUR_MODEL_ID --temperature 0
```

该客户端只用 Python 标准库，通过 DeepSeek Chat Completions 的 function calling 循环与模型交换 tool call 和 tool output。模型 ID 必须是你的 DeepSeek API 账号可用的准确 ID。

## 固定 Skill 库

第二阶段的 Skill 在 [skills.py](skills.py) 中。共有 30 个手工编写的固定 Skill；每个都有相同的五个字段：Name、Description、Activation Condition、Procedure、Termination Condition。

```bash
python3 minilab.py skills
python3 minilab.py show-skill csv-analysis
```

Skill 库只读，不会根据 Activation Condition 自动选择 Skill。它没有自动学习、自动进化、PPO 或 Skill graph；后续实验可以把“是否选对固定 Skill”单独作为变量。

## A–E 实验与结果

[experiment.py](experiment.py) 运行五个固定条件：`no_skill`、`all_skills`、`flat_retrieval`、`body_aware_retrieval`、`oracle_skill`。`gold_skills.py` 是冻结的人工 Oracle 标注。每一个 episode 追加为 [results/results.jsonl](results/results.jsonl) 的一行；不会覆盖旧数据。

```bash
python3 experiment.py --model deepseek-v4-flash --tasks csv-02 --repeats 1 --run-id pilot-01
python3 experiment.py --model deepseek-v4-flash --suite v4 --repeats 3 --run-id v4-small-30x3
python3 summarize_results.py results/results.jsonl --run-id baseline-v1
```

`--suite v4` 是冻结的 30 题正式 Mini Lab 集：12 道原有组合题和 18 道新增多步骤题。`--all-tasks` 会发出大量 API 请求，必须显式指定。A–E 使用相同的 Agent、任务、工具、grader、模型和 temperature；区别只在加载的 Skill。记录内容包括成败、输入/输出 token、模型调用数、工具调用数、延迟、成本、Skill 加载与检索排名。

Flat 和 Body-aware 默认使用 `hash-embedding-v1`：一个无依赖、确定性的本地向量检索基线。它不是预训练语义 embedding；接入外部 embedding 模型时，应换一个 retriever 版本并单独比较。

ScienceWorld 的 [哈希碰撞审计](docs/research/scienceworld_hash_collision_audit_2026-09-24.md) 已重放 304 条历史检索记录，并对 61 个去重后的题目与 Skill 版本组合比较四种哈希维度及完整词频表示。碰撞会造成漏检，也会偶然帮助命中；不能把单题路由差异直接当成正文索引的优势。脚本 `scienceworld_hash_audit.py` 可用 [导出的源记录](results/scienceworld_hash_audit_2026-09-24/source_records.jsonl) 独立复现，不需要 API Key 或 ScienceWorld 环境；旧在线检索器与实验结果保持原版本。

## ALFWorld：固定 Skill 的 A–E 实验

`alfworld_agent.py` 运行文字版 `AlfredTWEnv`。DeepSeek 只有一个 `act(command)` 动作工具，成功只由 ALFWorld 返回的 `won` 决定。`alfworld_skills.py` 有 30 个手工固定 Skill；没有自动学习、PPO 或 Skill graph。每次正式 API 运行会追加写入 `results/alfworld_results.jsonl`。

先创建独立环境并下载 ALFWorld 任务数据：

```bash
python3.9 -m venv .venv/alfworld-native
.venv/alfworld-native/bin/python -m pip install -r requirements-alfworld.txt
.venv/alfworld-native/bin/alfworld-download --data-dir .alfworld-data
```

先确认本地环境和任务数据能启动，不会调用 API：

```bash
.venv/alfworld-native/bin/python alfworld_agent.py --smoke
```

检查同一题是否能由 ALFWorld 的本地专家完成，不会调用 API：

```bash
.venv/alfworld-native/bin/python alfworld_agent.py --expert-check --task-index 0
```

跑一条真实的 No-Skill DeepSeek episode：

```bash
export DEEPSEEK_API_KEY='...'
.venv/alfworld-native/bin/python alfworld_agent.py --model deepseek-v4-flash --temperature 0 --run-id alfworld-noskill-01
```

跑一题的 Flat Retrieval（从 30 个 Skill 里固定检索 Top-3）：

```bash
.venv/alfworld-native/bin/python alfworld_agent.py --model deepseek-v4-flash --temperature 0 --task-index 0 --condition flat_retrieval --run-id alfworld-flat-01
```

运行 10 道题、5 个条件、各 1 次的 Pilot：

```bash
.venv/alfworld-native/bin/python alfworld_experiment.py --model deepseek-v4-flash --temperature 0 --tasks 0,1,2,3,4,5,6,7,8,9 --repeats 1 --run-id alfworld-pilot-10x1
python3 summarize_results.py results/alfworld_results.jsonl --run-id alfworld-pilot-10x1
```

五个条件是 `no_skill`、`all_skills`、`flat_retrieval`、`body_aware_retrieval`、`oracle_skill`。每次运行记录 Success Rate、Input Tokens、Output Tokens、Total Tokens、End-to-End Latency、Cost per Successful Task、Tool Calls，并保存已加载 Skill、人工 Gold Skill 和检索排名。

如果网络中断后以同一个 run ID 续跑，使用 `--deduplicate` 读取时按文件中最早记录保留每个 `task × condition × repeat`，不会改动原始 JSONL：

```bash
python3 summarize_results.py results/alfworld_results.jsonl --run-id alfworld-v2-pilot-10x1 --deduplicate
python3 failure_matrix.py results/alfworld_results.jsonl --run-id alfworld-v2-pilot-10x1 --deduplicate
```

正式实验使用冻结的 `alfworld-v2-30`：六类 ALFWorld 目标各 5 题。先用一次重复确认脚本与成本，再决定是否跑三次重复：

```bash
.venv/alfworld-native/bin/python alfworld_experiment.py --model deepseek-v4-flash --temperature 0 --suite alfworld-v2-30 --repeats 1 --run-id alfworld-v2-30x1
```

`v5-goal-only-router` 只把初始观察中 `Your task is to:` 后面的目标交给检索器，避免房间物品列表污染查询。独立测试集 `alfworld-v5-test-30` 与 `alfworld-v2-30`、`alfworld-v3-heldout-30` 均不重叠，仍是六类任务各 5 题。先跑 6 题 Pilot：

```bash
.venv/alfworld-native/bin/python alfworld_experiment.py --model deepseek-v4-flash --temperature 0 --tasks 28,37,32,51,60,66 --conditions no_skill,all_skills,body_aware_retrieval,bm25_body_retrieval,oracle_skill --repeats 1 --run-id alfworld-v5-router-pilot-6x1
```

Pilot 无程序错误后，再跑独立测试集三次重复。`--resume` 可在断网或手工中止后续跑：

```bash
.venv/alfworld-native/bin/python alfworld_experiment.py --model deepseek-v4-flash --temperature 0 --suite alfworld-v5-test-30 --conditions no_skill,all_skills,body_aware_retrieval,bm25_body_retrieval,oracle_skill --repeats 3 --run-id alfworld-v5-test-30x3 --resume
```

### v5 正式结果

`alfworld-v5-test-30x3` 共 450 个 episode，数据完整且无重复。All Skills 的原始成功率最高（98.89%），但相对 No Skill 的差值只有 +1.11 个百分点，任务级配对 bootstrap 的 95% CI 为 -3.33 至 6.67 个百分点。No Skill 与 BM25 Body 均为 97.78%，No Skill 的平均总 token 最低（28,612），单次成功成本也最低（$0.000599）。现有结果不支持固定 Skill 带来稳定成功率收益。

BM25 离线评测与 Agent 在线运行现在共用同一个目标句提取函数。30 道题的 Top-3 结果完全一致，主 Skill Hit@3 为 86.7%。冻结数据、统计表、图和失败记录在 [`results/formal_v5`](results/formal_v5)。Word 仅用于本地校订，仓库只发布定稿 PDF。

复现正式统计和图：

```bash
python3 analyze_alfworld_formal.py results/alfworld_results.jsonl --run-id alfworld-v5-test-30x3 --output-dir results/formal_v5
python3 plot_alfworld_results.py results/alfworld_results.jsonl --run-id alfworld-v5-test-30x3 --output-dir results/formal_v5/figures --deduplicate
```

### v6 Oracle 诊断

v5 测试集已经冻结，不再用于修改 Skill。`alfworld-v6-dev-20` 使用独立的 `valid_seen` 开发分区，包含 10 道加热任务和 10 道双物体放置任务。`oracle_v5` 加载原始 Skill；`oracle_v6` 只替换 `execute-heat-place` 和 `two-object-placement`，其余 28 个 Skill 保持不变。先运行 6 题 Pilot：

```bash
.venv/alfworld-native/bin/python alfworld_experiment.py --model deepseek-v4-flash --temperature 0 --tasks 2,39,46,16,43,82 --split valid_seen --conditions no_skill,oracle_v5,oracle_v6 --max-steps 100 --repeats 1 --run-id alfworld-v6-oracle-pilot-6x1 --resume
```

Pilot 正常后再运行 20 题三次重复：

```bash
.venv/alfworld-native/bin/python alfworld_experiment.py --model deepseek-v4-flash --temperature 0 --suite alfworld-v6-dev-20 --conditions no_skill,oracle_v5,oracle_v6 --max-steps 100 --repeats 3 --run-id alfworld-v6-oracle-dev-20x3 --resume
```

v6 Pilot 暴露出加热流程与环境动作语义不一致。v7 保留 v6 的目标辨别和双物体 Skill，只把加热步骤改为手持目标直接调用 `heat <target> with <microwave>`。原 v6 内容和哈希保持不变。运行同一批 6 题：

```bash
.venv/alfworld-native/bin/python alfworld_experiment.py --model deepseek-v4-flash --temperature 0 --tasks 2,39,46,16,43,82 --split valid_seen --conditions no_skill,oracle_v5,oracle_v7 --max-steps 100 --repeats 1 --run-id alfworld-v7-oracle-pilot-6x1 --resume
```

### v7 独立目标类型测试

`alfworld-v7-targeted-test-10` 冻结了未参与 v2、v3、v5 正式实验和 v6/v7 开发的 10 道 `valid_unseen` 任务，包括 8 道加热任务和 2 道双物体任务。该结果只支持这两类目标，不能外推到全部 ALFWorld 任务。v7 在本测试后不再修改。

冻结轨迹、统计表、失败分类和图表位于 [`results/formal_v7`](results/formal_v7)。

```bash
.venv/alfworld-native/bin/python alfworld_experiment.py --model deepseek-v4-flash --temperature 0 --suite alfworld-v7-targeted-test-10 --conditions no_skill,oracle_v5,oracle_v7 --max-steps 100 --repeats 3 --run-id alfworld-v7-targeted-test-10x3 --resume
```

```bash
python3 summarize_results.py results/alfworld_results.jsonl --run-id alfworld-v7-targeted-test-10x3 --deduplicate --repeat-stats
```

### v8 独立确认实验

`alfworld-v8-confirm-20` 冻结了 20 道未参与 v6/v7 开发的 `valid_seen` 任务，包括 6 道加热任务和 14 道双物体任务。v7 Skill 和 Agent 协议在运行前冻结。该套件与开发题在任务层面不重叠，但同属 `valid_seen`，不作为新的 OOD 证据。

```bash
.venv/alfworld-native/bin/python alfworld_experiment.py --model deepseek-v4-flash --temperature 0 --suite alfworld-v8-confirm-20 --conditions no_skill,oracle_v5,oracle_v7 --max-steps 100 --repeats 3 --run-id alfworld-v8-confirm-20x3 --resume
```

```bash
python3 summarize_results.py results/alfworld_results.jsonl --run-id alfworld-v8-confirm-20x3 --deduplicate --repeat-stats
```

### v8 确认结果

`alfworld-v8-confirm-20x3` 共 180 个 episode。No Skill 与 Oracle v7 都是 60/60；Oracle v7 的平均 Total Tokens 高 33.3%，端到端延迟高 16.5%，单次成功成本高 15.0%。任务级配对 bootstrap 的成本区间均跨过 0，因此不能断言 Skill 必然增加成本；这批确认数据能支持的结论是，v7 在定向测试中的效率优势没有复现。

冻结轨迹、统计表、任务级差异、失败摘要和图件位于 [`results/formal_v8`](results/formal_v8)。复现统计与图：

```bash
python3 analyze_alfworld_v8.py results/alfworld_results.jsonl
python3 plot_alfworld_v8.py results/formal_v8
```

逐题检查 Flat 与 Oracle 的失败：

```bash
python3 failure_matrix.py results/results.jsonl --run-id baseline-v1
```

输出只包含发生过失败的 `task_id × condition`，附带加载的 Skill、Gold Skill、检索排名和每次失败的工具 trace。

## ScienceWorld：第一个 6 题 Pilot

ScienceWorld 第一版只比较 `no_skill` 和 `oracle_skill`，不做检索。Pilot 含 6 个任务类型：沸腾、熔化、冻结、温度测量、寻找生物和寻找非生物。每个 Oracle Skill 都是人工固定文本。成功条件是 ScienceWorld 返回 `score >= 100`，不读取模型声明。v1 原始数据和失败摘要已冻结在 [`results/formal_scienceworld_v1`](results/formal_scienceworld_v1)。

依赖安装在项目文件夹内：

```bash
python3 -m venv .venv/scienceworld
.venv/scienceworld/bin/python -m pip install -r requirements-scienceworld.txt
```

先做本地启动和客观评分检查，两条都不调用 DeepSeek：

```bash
.venv/scienceworld/bin/python scienceworld_agent.py --smoke --task boil
.venv/scienceworld/bin/python scienceworld_agent.py --gold-check --task boil
```

根据 v1 Pilot 修订的 v2 只替换熔化、冻结和生物识别三个 Skill，原 v1 文本和哈希保持不变。Agent 同时记录 `environment_moves`，因为 ScienceWorld 的 `wait` 会消耗 10 个环境时间步。运行新的 `6 tasks × 2 conditions × 1 repeat = 12 episodes`：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --model deepseek-v4-flash \
  --temperature 0 \
  --repeats 1 \
  --run-id scienceworld-v2-pilot-6x1 \
  --resume
```

结果追加到 `results/scienceworld_results.jsonl`。查看六项核心指标和环境平均分：

```bash
python3 summarize_results.py results/scienceworld_results.jsonl \
  --run-id scienceworld-v2-pilot-6x1 \
  --deduplicate
```

Pilot 只检查软件链路和 Oracle Skill 是否有值得继续测的信号，不用来声称正式结论。

### v3 held-out 测试

`scienceworld-v3-heldout-6` 对六类任务分别使用官方 test split 的第一个 variation，与用于修改 Skill 的 variation 0 不重叠。选题和本地 gold 验收记录在 [`results/scienceworld_v3_heldout_manifest.jsonl`](results/scienceworld_v3_heldout_manifest.jsonl)。v2 Skill 不再修改。

先复现六题的本地 gold 检查，不调用 API：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --suite scienceworld-v3-heldout-6 \
  --max-steps 100 \
  --gold-check
```

运行 `6 tasks × 2 conditions × 3 repeats = 36 episodes`：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --model deepseek-v4-flash \
  --temperature 0 \
  --suite scienceworld-v3-heldout-6 \
  --conditions no_skill,oracle_v2 \
  --max-steps 100 \
  --repeats 3 \
  --run-id scienceworld-v3-heldout-6x3 \
  --resume
```

```bash
python3 summarize_results.py results/scienceworld_results.jsonl \
  --run-id scienceworld-v3-heldout-6x3 \
  --deduplicate \
  --repeat-stats
```

v3 的 36 条完整结果、条件汇总、逐题汇总、配对差异和失败证据已冻结在 [`results/formal_scienceworld_v3`](results/formal_scienceworld_v3)。No Skill 与 Oracle v2 的成功率均为 `66.67%`；Oracle v2 的平均 Total Tokens 低 `21.8%`，但节省主要来自 `find-living-thing`，不能据此声称 Skill 普遍有效。

### Oracle v3 与下一组 held-out 测试

Oracle v3 只改写 `boil-substance`、`melt-substance` 和 `freeze-substance`。修改依据是 v3 中已经冻结的失败轨迹：模型把熔化误当成沸腾，或试图冻结原本就是固体的样本。下一套 `scienceworld-v4-heldout-6` 在 Oracle v3 编写前已经提交，使用每类任务的第二个官方 test variation。选择和 gold 验收记录见 [`results/scienceworld_v4_heldout_manifest.jsonl`](results/scienceworld_v4_heldout_manifest.jsonl)。

先执行不调用 API 的 gold 检查：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --suite scienceworld-v4-heldout-6 \
  --max-steps 200 \
  --gold-check
```

v4 使用统一的 200 环境步预算，因为该套件中观察到的最长 gold path 为 166 个动作。这个预算只用于 v4 内部条件比较，不把 v4 的绝对成功率与 v3 的 100 步结果直接比较。

运行 `6 tasks × 3 conditions × 3 repeats = 54 episodes`：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --model deepseek-v4-flash \
  --temperature 0 \
  --suite scienceworld-v4-heldout-6 \
  --conditions no_skill,oracle_v2,oracle_v3 \
  --max-steps 200 \
  --repeats 3 \
  --run-id scienceworld-v4-heldout-6x3 \
  --resume
```

```bash
python3 summarize_results.py results/scienceworld_results.jsonl \
  --run-id scienceworld-v4-heldout-6x3 \
  --deduplicate \
  --repeat-stats
```

完成后冻结：

```bash
python3 analyze_scienceworld_formal.py results/scienceworld_results.jsonl \
  --run-id scienceworld-v4-heldout-6x3 \
  --suite scienceworld-v4-heldout-6 \
  --conditions no_skill,oracle_v2,oracle_v3 \
  --repeats 3 \
  --output-dir results/formal_scienceworld_v4
```

v4 已完成全部 54 个 episode，记录完整且没有重复。冻结结果见 [`results/formal_scienceworld_v4`](results/formal_scienceworld_v4)：

- No Skill：成功率 `66.67%`，平均分 `87.17`，平均 Total Tokens `254,214.5`。
- Oracle v2：成功率 `66.67%`，平均分 `87.50`，平均 Total Tokens `242,745.4`。
- Oracle v3：成功率 `94.44%`，平均分 `98.72`，平均 Total Tokens `183,179.2`。

相对 No Skill，Oracle v3 的成功率提高 `27.78` 个百分点，平均 Total Tokens 减少 `27.94%`，平均延迟减少 `15.99%`，每个成功任务的成本减少 `42.96%`。逐题结果显示，Oracle v3 把 `freeze:v022` 从 `0/3` 修到 `3/3`，把 `boil:v022` 从 `0/3` 修到 `2/3`；其余四题没有降低成功率。唯一一次 Oracle v3 失败是 `boil:v022` 耗尽 200 个环境步。

这组结果支持“正确的固定过程 Skill 能改善特定长程任务”的判断，但不能外推为任意 Skill、检索式 Skill 或任意环境都有效。实验只覆盖六个任务类型，Oracle v3 还是人工指定的 gold Skill；下一步应把同一 Skill 接入检索条件，并扩大未见 variation 的数量。

### ScienceWorld Router Pilot

Router 使用冻结的 v3 Skill 库。`all_skills` 加载全部 6 个 Skill；`flat_retrieval` 只索引 Name 与 Description；`body_aware_retrieval` 同时索引 Procedure 与 Termination Condition。两种检索都使用项目内确定性的 `hash-embedding-v1`，返回 Top-3，不调用外部 embedding API。

对 v4 六道任务的离线核验中，Flat Gold Hit@3 为 `4/6`，Body-aware 为 `5/6`。两者都漏掉 `boil`，Flat 还漏掉 `melt`。这批任务已经用于 Oracle v3 测试，因此下面的 30-episode 运行只检查程序、记录和路由行为，不用于正式结论：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --model deepseek-v4-flash \
  --temperature 0 \
  --suite scienceworld-v4-heldout-6 \
  --conditions no_skill,all_skills,flat_retrieval,body_aware_retrieval,oracle_v3 \
  --max-steps 200 \
  --repeats 1 \
  --run-id scienceworld-v5-router-pilot-6x1 \
  --resume
```

每个 episode 会记录 `skills_loaded`、完整检索排名、Gold Skill 排名、检索器版本和实际任务描述。Pilot 通过后，再预注册未见 variation 做三次重复的正式比较。

Pilot 已完成全部 30 个 episode，记录完整且没有重复。证据冻结在 [`results/pilot_scienceworld_v5`](results/pilot_scienceworld_v5)，并明确标记为复用 v4 任务的调试实验：

- No Skill：成功率 `66.67%`，平均 Total Tokens `151,263.7`。
- All Skills：成功率 `100%`，平均 Total Tokens `268,189.3`。
- Flat Retrieval：成功率 `66.67%`，平均 Total Tokens `367,334.5`。
- Body-aware Retrieval：成功率 `100%`，平均 Total Tokens `153,472.0`。
- Oracle v3：成功率 `100%`，平均 Total Tokens `265,444.8`。

Flat 在 `boil` 上漏检 Gold Skill 并失败；在 `freeze` 上虽然 Gold Skill 排第 3，仍因执行过程耗尽步数而失败。Body-aware 的 Gold Hit@3 为 `5/6`，但六题全部成功；它在成功率相同的三组中 token、延迟和成功成本最低。单次 Pilot 只能说明 Router 链路可运行，并为正式实验提供方法选择，不能估计稳定收益。

### ScienceWorld Router 正式实验

`scienceworld-v6-router-formal-12` 在 Pilot 后固定，但没有根据 Pilot 成败挑题。它机械选取六类任务各自第 3、4 个官方 test variation，共 12 道新题；选择提交见 [`results/scienceworld_v6_router_manifest.jsonl`](results/scienceworld_v6_router_manifest.jsonl)。所有题均未出现在此前的 Pilot、v3 或 v4 套件中。

本地 Gold 验证显示 12 题均可达到 100 分，最长路径是 `melt:v024` 的 366 个环境步，因此正式条件统一使用 400 步。Gold 记录见 [`results/scienceworld_v6_gold_validation.jsonl`](results/scienceworld_v6_gold_validation.jsonl)。离线 Router 审计已冻结且没有据此调参：Flat Gold Hit@3 为 `8/12`，Body-aware 为 `10/12`；逐题排名见 [`results/scienceworld_v6_router_offline.jsonl`](results/scienceworld_v6_router_offline.jsonl)。

运行 `12 tasks × 5 conditions × 3 repeats = 180 episodes`：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --model deepseek-v4-flash \
  --temperature 0 \
  --suite scienceworld-v6-router-formal-12 \
  --conditions no_skill,all_skills,flat_retrieval,body_aware_retrieval,oracle_v3 \
  --max-steps 400 \
  --repeats 3 \
  --run-id scienceworld-v6-router-formal-12x3 \
  --resume
```

```bash
python3 summarize_results.py results/scienceworld_results.jsonl \
  --run-id scienceworld-v6-router-formal-12x3 \
  --deduplicate \
  --repeat-stats
```

完成后冻结：

```bash
python3 analyze_scienceworld_formal.py results/scienceworld_results.jsonl \
  --run-id scienceworld-v6-router-formal-12x3 \
  --suite scienceworld-v6-router-formal-12 \
  --conditions no_skill,all_skills,flat_retrieval,body_aware_retrieval,oracle_v3 \
  --repeats 3 \
  --output-dir results/formal_scienceworld_v6
```

正式实验已完成全部 180 个 episode，未发现缺失或重复记录。原始轨迹的 SHA-256 为 `c978ce0568f89fecaff48848327817cdd3493a18162df1bc0b99bcdaf9b043fd`，冻结文件与分析结果位于 [`results/formal_scienceworld_v6`](results/formal_scienceworld_v6)。

- No Skill：成功率 `69.44%`，平均 Total Tokens `743,891`，平均延迟 `73.83 s`，每个成功任务成本 `$0.00716`。
- All Skills：成功率 `91.67%`，平均 Total Tokens `657,441`，平均延迟 `62.10 s`，每个成功任务成本 `$0.00464`。
- Flat Retrieval：成功率 `75.00%`，平均 Total Tokens `786,855`，平均延迟 `71.04 s`，每个成功任务成本 `$0.00661`。
- Body-aware Retrieval：成功率 `88.89%`，平均 Total Tokens `244,086`，平均延迟 `40.45 s`，每个成功任务成本 `$0.00271`。
- Oracle v3：成功率 `94.44%`，平均 Total Tokens `282,217`，平均延迟 `42.92 s`，每个成功任务成本 `$0.00270`。

与 No Skill 配对比较，Body-aware 的成功率高 `19.44` 个百分点，任务聚类 Bootstrap 95% CI 为 `[8.33, 30.56]` 个百分点；12 道任务中 6 道改善、0 道变差、6 道持平，双侧精确符号检验 `p=0.031`。其平均 Total Tokens 低 `67.19%`，延迟低 `45.21%`，每个成功任务成本低 `62.10%`。Flat 的成功率差仅 `+5.56` 个百分点，95% CI 跨过 0，且平均 Total Tokens 高 `5.78%`，没有稳定收益。

检索结果解释了两者差异：Flat 的 Gold Hit@3 为 `66.67%`，命中时成功率 `87.50%`、漏检时 `50.00%`；Body-aware 的 Gold Hit@3 为 `83.33%`，命中时成功率 `93.33%`、漏检时 `66.67%`。29 次失败中，18 次耗尽环境动作预算，8 次模型提前停止，3 次属于其他执行错误。

这组数据支持一个有限结论：在这 12 道预先固定的 ScienceWorld test variation 上，读取 Skill 正文的检索方式比 No Skill 更成功，也更省推理成本。它不证明所有 Skill 或所有环境都有效；唯一任务数仍是 12，Router 使用的是本地确定性哈希向量，不是预训练语义向量。完整指标见 [`condition_summary.csv`](results/formal_scienceworld_v6/condition_summary.csv)，配对统计见 [`paired_statistics.csv`](results/formal_scienceworld_v6/paired_statistics.csv)。

图表和 Word 报告可由冻结数据重新生成：

```bash
python3 plot_scienceworld_v6.py results/formal_scienceworld_v6
python3 build_scienceworld_v6_report.py \
  results/formal_scienceworld_v6/analysis_summary.json \
  --figures-dir results/formal_scienceworld_v6/figures \
  --output ScienceWorld_固定Skill检索正式实验报告_v9.docx
```

脚本名中的 `v6` 是实验批次，文档名中的 `v9` 是报告修订号，两者不是同一套编号。

### ScienceWorld v10 独立确认实验

确认集在 Gold 验证和 API 运行前固定。它机械选取六类任务各自第 5、6 个官方 test variation，共 12 道新题，与 Pilot、v3、v4 和 v6 均不重叠。预注册清单、条件、指标和文件哈希见 [`results/scienceworld_v10_confirmation_manifest.json`](results/scienceworld_v10_confirmation_manifest.json)。

本轮只比较 No Skill、Flat Retrieval 和 Body-aware Retrieval。每题每条件重复 3 次，共 `12 × 3 × 3 = 108` 个 episode。先运行不调用模型的本地 Gold 验证：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --suite scienceworld-v10-confirm-12 \
  --max-steps 400 \
  --gold-check
```

本地 Gold 验证已经通过：12 道题均达到 100 分，最长路径为 `melt:v025` 的 365 个环境步。验收记录见 [`results/scienceworld_v10_gold_validation.jsonl`](results/scienceworld_v10_gold_validation.jsonl)。正式实验尚未运行；运行命令如下：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --model deepseek-v4-flash \
  --temperature 0 \
  --suite scienceworld-v10-confirm-12 \
  --conditions no_skill,flat_retrieval,body_aware_retrieval \
  --max-steps 400 \
  --repeats 3 \
  --run-id scienceworld-v10-confirm-12x3 \
  --resume
```

完成后校验 108 个 episode，并冻结分析文件：

```bash
python3 analyze_scienceworld_formal.py results/scienceworld_results.jsonl \
  --run-id scienceworld-v10-confirm-12x3 \
  --suite scienceworld-v10-confirm-12 \
  --conditions no_skill,flat_retrieval,body_aware_retrieval \
  --repeats 3 \
  --output-dir results/formal_scienceworld_v10 \
  --purpose "independent confirmation of body-aware retrieval"
```

确认实验已完成 108 个 episode，记录完整且没有重复。冻结轨迹的 SHA-256 为 `d6614857fe39458c0e8f23e04c96d75d15d6b7f9cb90c131f0a391b6cfd9a4e2`，分析文件位于 [`results/formal_scienceworld_v10`](results/formal_scienceworld_v10)。

- No Skill：成功率 `80.56%`，平均 Total Tokens `462,953`。
- Flat Retrieval：成功率 `94.44%`，平均 Total Tokens `302,352`。
- Body-aware Retrieval：成功率 `94.44%`，平均 Total Tokens `281,980`。

Body-aware 相对 No Skill 的成功率高 `13.89` 个百分点，平均 Total Tokens 低 `39.09%`，延迟低 `35.32%`，每个成功任务成本低 `40.06%`。成功率的任务聚类 Bootstrap 95% CI 为 `[0.00, 33.33]` 个百分点；任务级符号检验 `p=0.250`，episode 级精确 McNemar 检验 `p=0.0625`。Total Tokens 的任务聚类 95% CI 为 `[-518,502, 12,435]`，12 道题中 5 道更省、7 道更费，任务级符号检验 `p=0.774`。平均节省来自少数高开销任务，不是多数任务上的一致下降。两项预注册假设的点估计方向都与 v6 一致，但任务级区间和精确检验没有在常用的 0.05 阈值下完成统计确认。

Flat 与 Body-aware 的成功率相同。Body-aware 的平均 Total Tokens 比 Flat 低 `6.74%`，延迟低 `10.31%`，每个成功任务成本低 `5.65%`。Flat 的 Gold Hit@3 为 `66.67%`，Body-aware 为 `75.00%`；本轮检索命中率差距缩小，不能把成本差异单独归因于 Gold Skill 排名。

### ScienceWorld v11b 平衡确认实验

原 v11 计划按六类各5题抽取30题，但本地预检发现 `boil`、`melt` 和 `freeze` 的官方 test variation 只到29，计划中的30和31无效。该计划在调用 API 前作废，记录保留在 [`results/scienceworld_v11_large_confirmation_manifest.json`](results/scienceworld_v11_large_confirmation_manifest.json)。

替代协议 v11b 机械选取每类前三个未用的官方 test variation，共18题。这样不复用旧题，也不改变六类任务的权重。Skill 库、检索器、Agent 协议和主要比较均保持不变。本轮只运行 No Skill、Flat Retrieval 和 Body-aware Retrieval，每个条件重复3次，共 `18 × 3 × 3 = 162` 个 episode。预注册信息见 [`results/scienceworld_v11b_confirmation_manifest.json`](results/scienceworld_v11b_confirmation_manifest.json)。

先做两项不调用 DeepSeek 的本地检查。检索审计确认所有 variation 属于 test split，并保存两种 Router 的 Top-3 和 Gold 排名：

```bash
.venv/scienceworld/bin/python scienceworld_retrieval_audit.py \
  --suite scienceworld-v11b-confirm-18 \
  --output results/scienceworld_v11b_retrieval_audit.jsonl
```

检索审计已通过18题的 test split 校验。Flat Gold Hit@3 为 `12/18`（66.67%），Body-aware 为 `15/18`（83.33%）；逐题记录见 [`results/scienceworld_v11b_retrieval_audit.jsonl`](results/scienceworld_v11b_retrieval_audit.jsonl)。

Gold 路径检查确认18题可在400个环境动作内由环境专家完成：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --suite scienceworld-v11b-confirm-18 \
  --max-steps 400 \
  --gold-check \
  --check-results results/scienceworld_v11b_gold_validation.jsonl
```

Gold 检查18题全部达到100分，最长路径使用122个环境动作；逐题记录见 [`results/scienceworld_v11b_gold_validation.jsonl`](results/scienceworld_v11b_gold_validation.jsonl)。

两项检查通过后运行正式实验。网络中断或手工停止后，原命令再次执行即可从缺失 episode 继续：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --model deepseek-v4-flash \
  --temperature 0 \
  --suite scienceworld-v11b-confirm-18 \
  --conditions no_skill,flat_retrieval,body_aware_retrieval \
  --max-steps 400 \
  --repeats 3 \
  --run-id scienceworld-v11b-confirm-18x3 \
  --resume
```

162 个 episode 完成后校验并冻结分析文件：

```bash
python3 analyze_scienceworld_formal.py results/scienceworld_results.jsonl \
  --run-id scienceworld-v11b-confirm-18x3 \
  --suite scienceworld-v11b-confirm-18 \
  --conditions no_skill,flat_retrieval,body_aware_retrieval \
  --repeats 3 \
  --output-dir results/formal_scienceworld_v11 \
  --purpose "balanced held-out confirmation of fixed-Skill retrieval"
```

v11b 已完成全部 162 个 episode，无缺失、无重复。Body-aware Retrieval 成功率为 `88.89%`，No Skill 为 `77.78%`，配对差为 `+11.11` 个百分点，任务聚类 Bootstrap 95% CI 为 `[1.85, 22.22]`。Body-aware 的平均 Total Tokens 低 `66.57%`，延迟低 `45.56%`。收益集中在少数长轨迹任务；详细配对统计、敏感性分析和彩色图见 [v11b Markdown 报告](reports/scienceworld_v11b/ScienceWorld_固定Skill检索平衡确认报告_v11b.md)。

### ScienceWorld v12 机制消融 Pilot

v12 不再检验“Body-aware 是否有效”，而是检查 v11b 的收益是否来自任务专用 Procedure。它有意复用 v11b 中每类一道题，因此是机制 Pilot，不是新的独立确认。预注册设置见 [`scienceworld_v12_mechanism_pilot_manifest.json`](results/scienceworld_v12_mechanism_pilot_manifest.json)。

- `body_aware_retrieval`：加载完整 Top-3 Skill。
- `body_metadata_only`：Top-3 完全相同，只加载 Name、Description 和 Activation Condition。
- `body_placebo`：Top-3 和元数据不变，用与原文空格分词数相同的通用词替换 Procedure 和 Termination Condition。

运行 `6 tasks × 4 conditions × 1 repeat = 24 episodes`：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --model deepseek-v4-flash \
  --temperature 0 \
  --suite scienceworld-v12-mechanism-pilot-6 \
  --conditions no_skill,body_aware_retrieval,body_metadata_only,body_placebo \
  --max-steps 400 \
  --repeats 1 \
  --run-id scienceworld-v12-mechanism-pilot-6x1 \
  --resume
```

Pilot 只看程序、提示控制和方向性信号，不报统计显著性。

### ScienceWorld v13 Oracle 内容消融 Pilot

v12 的 Body-aware Top-3 没有稳定包含正确 Skill，因此无法单独判断 Procedure 的作用。v13 去掉 Router：三个 Skill 条件都只加载人工标注的同一个正确 v3 Skill，差别仅是正文呈现方式。预注册设置见 [`scienceworld_v13_oracle_mechanism_pilot_manifest.json`](results/scienceworld_v13_oracle_mechanism_pilot_manifest.json)。

- `oracle_v3_full`：加载正确 Skill 的完整五段内容。
- `oracle_v3_metadata`：加载同一 Skill 的 Name、Description 和 Activation Condition。
- `oracle_v3_placebo`：保留同一元数据，用等词数通用文本替换 Procedure 和 Termination Condition。
- `no_skill`：不加载 Skill，作为背景基线。

先运行 `6 tasks × 4 conditions × 1 repeat = 24 episodes`：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --model deepseek-v4-flash \
  --temperature 0 \
  --suite scienceworld-v13-oracle-mechanism-pilot-6 \
  --conditions no_skill,oracle_v3_full,oracle_v3_metadata,oracle_v3_placebo \
  --max-steps 400 \
  --repeats 1 \
  --run-id scienceworld-v13-oracle-mechanism-pilot-6x1 \
  --resume
```

汇总：

```bash
python3 summarize_results.py results/scienceworld_results.jsonl \
  --run-id scienceworld-v13-oracle-mechanism-pilot-6x1 \
  --deduplicate
```

主比较是 `oracle_v3_full` 对 `oracle_v3_metadata`；`oracle_v3_placebo` 用于检查无关正文是否造成干扰。Pilot 通过后才冻结扩大实验。

### ScienceWorld v13b Oracle 内容消融定向确认

v13 Pilot 的差异集中在 `boil` 与 `freeze`。v13b 因此只检验状态转换机制，不用于估计整个 ScienceWorld 的总体性能。六道题复用 v11b 的官方 test variations；这是 Pilot 后定向选择，预注册文件为 [`scienceworld_v13b_oracle_mechanism_manifest.json`](results/scienceworld_v13b_oracle_mechanism_manifest.json)。

运行 `6 tasks × 3 conditions × 3 repeats = 54 episodes`：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --model deepseek-v4-flash \
  --temperature 0 \
  --suite scienceworld-v13b-oracle-mechanism-6 \
  --conditions oracle_v3_full,oracle_v3_metadata,oracle_v3_placebo \
  --max-steps 400 \
  --repeats 3 \
  --run-id scienceworld-v13b-oracle-mechanism-6x3 \
  --resume
```

汇总：

```bash
python3 summarize_results.py results/scienceworld_results.jsonl \
  --run-id scienceworld-v13b-oracle-mechanism-6x3 \
  --deduplicate \
  --repeat-stats
```

主比较是 Full 对 Metadata；Full 对等词数 Placebo 是更严格的 Procedure 语义比较。No Skill 不属于该机制问题，因此不重复运行。

正式结果为 54/54 条唯一 episode。Full、Metadata、Placebo 的成功率分别为 83.33%、38.89% 和 50.00%。Full 相对 Metadata 的任务簇配对差为 +44.44 个百分点，Bootstrap 95% CI 为 [16.67, 72.22]；相对等词数 Placebo 为 +33.33 个百分点，95% CI 为 [11.11, 55.56]。完整报告见 [`ScienceWorld_固定Skill_Procedure定向确认报告_v13b.md`](reports/scienceworld_v13b/ScienceWorld_固定Skill_Procedure定向确认报告_v13b.md)。

冻结正式结果并重建图表：

```bash
python3 analyze_scienceworld_formal.py results/scienceworld_results.jsonl \
  --run-id scienceworld-v13b-oracle-mechanism-6x3 \
  --suite scienceworld-v13b-oracle-mechanism-6 \
  --conditions oracle_v3_full,oracle_v3_metadata,oracle_v3_placebo \
  --repeats 3 \
  --output-dir results/formal_scienceworld_v13b \
  --purpose "targeted confirmation of fixed Skill Procedure content on state-change tasks"
python3 analyze_scienceworld_v13b.py
MPLCONFIGDIR=/tmp/fixedskilllab-matplotlib python3 plot_scienceworld_v13b.py
```

### ScienceWorld T1：Oracle T 型 Skill 2×2 Pilot

T1 检查“跨任务执行规则”和“任务专用 Procedure”能否形成互补。它不改模型、不用 Router，也不学习 Skill。定义、边界和后续确认路线见 [`t_shaped_skill_research.md`](docs/research/t_shaped_skill_research.md)，冻结协议见 [`scienceworld_t1_t_shaped_pilot_manifest.json`](results/scienceworld_t1_t_shaped_pilot_manifest.json)。

- `no_skill`：横向层 0，纵向层 0。
- `t_horizontal`：只加载 `scienceworld-execution-control`。
- `t_vertical`：只加载人工标注的 v3 任务 Skill。
- `t_full`：先加载横向 Skill，再加载同一条纵向路径。

十二道题直接复用已通过 Gold Check 的 v10 suite。这个设计适合做机制 Pilot，不属于新的 held-out 证据。主交互量为：

`(SR_t_full - SR_t_vertical) - (SR_t_horizontal - SR_no_skill)`

代码和清单已冻结，但还没有调用 API。运行 `12 tasks × 4 conditions × 1 repeat = 48 episodes`：

先重建离线 Prompt 审计（只写本地 JSONL，不调用 API）：

```bash
python3 scienceworld_t1_audit.py
```

再运行实验：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --model deepseek-v4-flash \
  --temperature 0 \
  --suite scienceworld-t1-t-shaped-pilot-12 \
  --conditions no_skill,t_horizontal,t_vertical,t_full \
  --max-steps 400 \
  --repeats 1 \
  --run-id scienceworld-t1-t-shaped-pilot-12x1 \
  --resume
```

查看四组基础指标：

```bash
python3 summarize_results.py results/scienceworld_results.jsonl \
  --run-id scienceworld-t1-t-shaped-pilot-12x1 \
  --deduplicate
```

确认 48 条齐全并计算整体及两类任务的 2×2 交互量：

```bash
python3 analyze_scienceworld_t1.py results/scienceworld_results.jsonl \
  --run-id scienceworld-t1-t-shaped-pilot-12x1
```

Pilot 只判断字段是否正确、四种 Prompt 是否确实不同、交互方向是否值得继续。不能用这 48 个 episode 宣称 T 型结构已经成立。

### ScienceWorld T2：横向进展控制器开发诊断

T1 的五次失败全部在分数长期不变后耗尽环境步数。T2 保留 T1 的横向 Skill 文本，并增加一个只作用于 `t2_horizontal` 和 `t2_full` 的确定性控制器：连续无进展的 `wait1` 最多执行 8 次，`wait` 最多 2 次，其他相同命令最多 3 次；超限动作不发送给环境，而是要求 Agent 检查状态和前置条件。

T2 有意复用 T1 中产生分歧的 `melt:v025` 和 `freeze:v026`，因此只是开发诊断，不是新证据。冻结设置见 [`scienceworld_t2_controller_dev_manifest.json`](results/scienceworld_t2_controller_dev_manifest.json)。

运行 `2 tasks × 4 conditions × 3 repeats = 24 episodes`：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --model deepseek-v4-flash \
  --temperature 0 \
  --suite scienceworld-t2-controller-dev-2 \
  --conditions no_skill,t2_horizontal,t2_vertical,t2_full \
  --max-steps 400 \
  --repeats 3 \
  --run-id scienceworld-t2-controller-dev-2x3 \
  --resume
```

只有当 `t2_full` 的成功率同时高于两个单层条件，并且控制器消除了重复动作导致的预算耗尽，才进入未见任务上的确认实验。否则，这版横向控制器不支持 T 型组合假设。

T2 实际开发结果没有通过这个门槛：`t2_vertical` 成功 5/6，`t2_full` 成功 4/6，成功率交互效应为 -16.7 个百分点。控制器有触发，但它只根据分数不变判断停滞，会把必要的等待也当成无进展。

### ScienceWorld T3：状态感知检查点

T3 是同一开发集上最后一次横向层调整。它移除 T1/T2 的横向 Skill 文本，使 `t3_full` 与 `t3_vertical` 加载完全相同的纵向 Procedure，两组只相差一个确定性控制器。控制器在三次连续等待后要求先 `examine`；对其他命令，只在命令、分数和 observation 都不变时拦截。它不读取任务族标签。

冻结协议见 [`scienceworld_t3_state_aware_dev_manifest.json`](results/scienceworld_t3_state_aware_dev_manifest.json)。运行 `2 tasks × 4 conditions × 3 repeats = 24 episodes`：

```bash
.venv/scienceworld/bin/python scienceworld_experiment.py \
  --model deepseek-v4-flash \
  --temperature 0 \
  --suite scienceworld-t3-state-aware-dev-2 \
  --conditions no_skill,t3_horizontal,t3_vertical,t3_full \
  --max-steps 400 \
  --repeats 3 \
  --run-id scienceworld-t3-state-aware-dev-2x3 \
  --resume
```

T3 必须同时满足：`t3_full` 成功数高于 `t3_vertical`、交互效应大于 0、`t3_full` 平均 Total Tokens 不超过 `t3_vertical` 的 1.25 倍。任一条失败就停止在这两个 case 上调横向层。

## 工具

- 文件：`read_file`、`write_file`、`list_files`、`copy_file`、`move_file`
- 文本：`search_text`、`replace_text`
- 数据：`convert_csv`、`sort_data`、`filter_data`、`find_max`、`find_min`、`sum_column`、`count_rows`
- 计算与答题：`calculate`、`submit`

所有路径都限制在本题 workspace 内。计算器解析算术 AST，不执行任意 Python。

## 任务分布

| 前缀 | 数量 | 内容 |
|---|---:|---|
| `text-*` | 8 | 读写、复制、移动、替换、列目录、搜索 |
| `calc-*` | 8 | 四则运算、幂、取模、整除 |
| `csv-*` | 12 | 转 JSON、排序、筛选、极值、求和、计数 |
| `mix-*` | 12 | 两到三步的组合任务 |
| `hard-*` | 18 | 两到四步的筛选、排序、转换、计算和文件链式任务 |

任务定义和 grader 在 `tasks.py`，参考 action 只供 `self-check` 验证。每道题在无 action 时必须失败，执行参考 action 后必须通过。
