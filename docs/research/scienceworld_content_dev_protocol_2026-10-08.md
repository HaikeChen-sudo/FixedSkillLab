# ScienceWorld 固定内容与移动指令消融协议

运行标识：`scienceworld-content-dev-4x3`。协议日期：2026-10-08。状态：准备阶段，未执行付费实验。

## 研究问题

上一轮 Top-1 dev 诊断中，正确与错配 Skill 都能完成非生物任务，但前者少执行拾取。实际文本同时存在目标类别和移动指令差异，不能把成本差额都归因于检索。新一轮直接控制加载文本，不运行 Router。

本轮分别检查正确内容相对无 Skill、错配内容的表现，以及单句移动指令对拾取动作和执行成本的影响。它是单个任务族的开发诊断，不能确认通用 Skill 优势、正文检索优势或研究新颖性。

## 四组条件

| 条件 | 加载内容 | 比较目的 |
| --- | --- | --- |
| no_skill | 不加载 Skill | 相同任务的基线 |
| content_correct | 原 v3 的完整 find-nonliving-object | 正确内容的净收益 |
| content_mismatched | 原 v3 的完整 find-living-object | 固定错配对照，不挑选更差的文本 |
| content_pickup_required | 完整非生物 Skill，仅替换 Procedure 第三步 | 单句移动约束的作用 |

原第三步：

> Pick up or directly move the same object to the task's destination.

替换后：

> Pick up the same object before moving it to the task's destination.

名称、描述、激活条件、前两步和终止条件逐字保持一致。替换句与原句词数相同，但不假定模型 Token 数相同。变体单独标为 `content-pickup-v1`，保存实际文本和对应库哈希。原 `scienceworld_skills.py` 不修改。它检验的是“允许两种方式”与“要求先拾取”的差异，不强迫模型直接移动。

生物 Skill 同时改变目标类别和其他过程文字，因此正确组与错配组是整体内容对照，不是单字段消融。No Skill 与其余三组使用相同的系统提示、模型、工具、判分和预算。所有组都绕过检索，不将 Oracle/直接加载写成 Router 效果。

## 选题与运行计划

只选 `find-non-living-thing`，因为本轮的单句消融作用于该任务的非生物 Skill。按题号升序选择历史使用记录之外的前四个官方 dev 实例；先冻结清单，再收集任务描述，不根据离线命中、可完成性或在线成败换题。

历史扫描范围是项目根目录 Python、docs 中 Markdown、results 中 JSON/JSONL 和注册 suites，并补入旧 Top-1 十二题清单。它不覆盖 tmp、二进制报告或项目外文件，因此“未使用”只指本次可核验范围。保存扫描文件哈希、已见实例和描述哈希。新 variation 可能复用旧任务描述；必须披露重复，不因描述重复而临时换题。

每题每组重复三次，共 4×4×3=48 个 episode。种子为 20261008，任务顺序固定打乱；四组按任务索引和重复序号轮换位置。每次重复跨四题，各组在四个运行位置各出现一次；单题三次重复并未覆盖四个位置，不能声称单题顺序完全平衡。

固定设置：`deepseek-v4-flash`、temperature=0、thinking disabled、simplification=easy。Agent 调用上限与环境 move 上限各 100。环境版本、jar、封装代码、Agent、协议与文本都写入冻结清单。成功仅由环境 score≥100 决定。此处不读取 Gold action sequence，也不执行参考解。

本轮新增显式固定文本入口。没有传入该参数时，旧 Agent 路径维持原逻辑。代码文件哈希会因接口添加而变化，旧清单的执行保护可能拒绝继续旧实验；不得修改旧清单绕过保护。历史原始结果与旧分析文件保留。需要复跑旧实验时使用对应 Git 版本。

## 指标与判断规则

六项主指标完整保留：

| 指标 | 定义 |
| --- | --- |
| Task Success Rate | 成功 episode 数/完成 episode 数；同时报告逐题次数 |
| Input Tokens | 多轮 API 请求累计输入 Token，不等于 Skill 本身长度 |
| Output Tokens | 多轮 API 请求累计输出 Token |
| Total Tokens | Input Tokens＋Output Tokens |
| End-to-End Latency | `runner_ms`，覆盖环境创建至关闭；不含批量预检 |
| Cost per Successful Task | 全部完成 episode 的估算成本/成功数，零成功为 null |

同时保留旧边界的 `latency_ms`、工具调用数、score、环境动作与 moves、原始命令、工具错误数和拾取命令数。`pickup_command_count` 统计以 `pick up ` 开头的发出命令，不代表每次都执行成功，更不能直接命名为“冗余拾取”。`tool_error_count` 只统计工具结果 ok=false；环境用自然语言拒绝的动作需另行审阅，不伪装成已自动识别的非法动作数。

预先指定两个对比：正确内容对 No Skill；正确内容对“必须先拾取”。错配组提供目标类别冲突的诊断背景。对每个实例先对三次重复求均值，再查看四个实例的方向。全部 episode 的六指标也照常汇总，保留失败，不只分析成功运行。

移动指令机制的开发方向判据：正确组相对“必须先拾取”组，在至少三个实例上同时减少平均工具调用和拾取命令数，并且四个实例中都没有降低成功次数，才记录为“方向性复现”。这是预登记的开发筛选规则，不是统计显著性或等效性检验。若不足三个实例、出现成功损失或方向矛盾，则记为未复现/存在权衡，本轮结束，不通过追加有利题目改变判据。

Token、完整时间与费用分别报告。步骤减少而完整时间增加时，必须写出代价。正确内容若与 No Skill 成功率都为 100%，只讨论已观察到的成本差异，不声称成功率提升。四个实例、一个任务族不足以验证通用结构，三次重复也不增加独立题数。

## 保存、停止与费用

专用入口默认为预览，不调用模型。`--prepare` 冻结选题与文本；`--collect` 只启动本地环境、核对官方划分并读取任务描述；`--check` 重复本地核对。只有用户执行 `--execute` 才调用 DeepSeek。

已完成 episode 先落盘，再做协议检查，异常不能导致已完成结果消失。续跑严格按清单跳过已保存的完整记录，拒绝重复、不同条件、不同提示、不同预算或损坏的 JSON。文件锁阻止两个进程同时运行这轮实验。

已记录估算费用达到 0.25 美元后，不启动下一条。按冻结历史价格计费，这不是当前价格核验或账户硬限额；运行中的 episode、中断请求、重试和未落盘调用可能产生额外费用。网络失败后未完成的 episode 会在续跑时重新执行，不能把结果文件成本当作完整账单。

API/协议异常时停止并检查，不自动换模型、改提示、扩大步数或跳过失败题。若预算停止或中途终止，只报告实际完成数，不把未完成当失败，也不计算“48 条完整实验”结论。

## 文件与命令

- [专用脚本](../../scienceworld_content_pilot.py)
- [测试](../../test_scienceworld_content_pilot.py)
- [冻结清单](../../results/scienceworld_content_dev/manifest.json)
- [任务描述](../../results/scienceworld_content_dev/queries.json)
- [本地预检](../../results/scienceworld_content_dev/preflight.json)

准备与预检由本地工具完成，不需 API Key。查看状态：

```sh
python3 scienceworld_content_pilot.py --status
python3 -m unittest test_scienceworld_content_pilot -v
```

用户决定开始时执行，只有下面这一条会产生模型费用：

```sh
.venv/scienceworld/bin/python scienceworld_content_pilot.py --execute --resume
```

完成后汇总：

```sh
python3 summarize_results.py results/scienceworld_content_dev/episodes.jsonl --run-id scienceworld-content-dev-4x3 --deduplicate --repeat-stats
```

现有汇总脚本仍输出旧计时边界 `average_latency_ms`。完整端到端时间需从原始 `runner_ms` 单独复算；不能将旧字段改名来代替。正式分析还须按实例汇总拾取命令数，核对上述预先固定的方向判据。
