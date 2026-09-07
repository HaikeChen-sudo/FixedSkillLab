# FixedSkillLab

固定 Skill 加载与检索的 LLM Agent 实验平台。仓库包含一个只用 Python 标准库的确定性 Mini Lab，以及 ALFWorld text-only 实验。成功条件均由程序或环境判断，模型不能给自己打分。

定稿报告：[Mini Lab 阶段报告](output/pdf/Mini_Lab_阶段科研报告.pdf) · [ALFWorld v7 综合研究报告](output/pdf/ALFWorld_固定Skill研究报告_v7.pdf)

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

逐题检查 Flat 与 Oracle 的失败：

```bash
python3 failure_matrix.py results/results.jsonl --run-id baseline-v1
```

输出只包含发生过失败的 `task_id × condition`，附带加载的 Skill、Gold Skill、检索排名和每次失败的工具 trace。

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
