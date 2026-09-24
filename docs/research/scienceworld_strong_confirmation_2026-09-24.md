# ScienceWorld 强语义检索：六题重复实验协议

日期：2026-09-24。运行编号：`scienceworld-strong-confirm-6x3`。本轮共 **6 题 × 3 条件 × 3 次 = 54 个 episode**。准备阶段不调用 DeepSeek，不读取这六题的任务描述或 Gold 轨迹。提交协议和机器清单后，由用户启动模型运行。

## 1. 本轮回答什么

主比较是 **Semantic Body 与 Semantic Flat**：在相同预训练编码器、同一候选库和 Top-3 预算下，将正文加入检索索引，是否改变加载的 Skill，并改善完成率或执行成本？两种检索各自对 No Skill 的比较是次要比较。

此前斜面 dev 单题 smoke 中，两种语义检索加载了相同的三条 Skill，顺序与提示哈希也相同。那次运行只说明接口能用。两种检索均成功、No Skill 失败，不足以证明 Skill 的普遍效果；同一道 No Skill 题在更早运行中也成功过。本轮不并入 smoke 记录。

## 2. 选题规则与边界

我们核对了 `results/`、`docs/research/` 下的 JSON/JSONL，以及项目根目录原有 Python 文件中的显式题号，共 180 个文件。扫描包含已运行题、Gold/检索审计题及未执行的预留计划。原 v14 预留的 12 题不动。文件哈希、排除编号和规则保存在[选题快照](../../results/scienceworld_strong_confirmation_selection.json)。这项审计不覆盖外部聊天附件或私人笔记，不能证明外部从未接触过相同题目。

先剔除没有剩余官方 test 变体的任务族，再按任务名的字典序取前六类；每类取未排除的最小 test 编号。没有根据查询文本、检索排名、Gold 路径、模型胜负换题。boil、melt、freeze 的官方 test 编号已耗尽；use-thermometer 在剩余七类中字典序排第七，本轮不选。

| 任务类别 | 固定变体 | 检索库 | Agent / 共同控制器 |
|---|---:|---|---|
| chemistry-mix | 30 | v4d，10 条 Skill | v14b / shared-state-checkpoint-v1 |
| find-living-thing | 236 | v3，6 条 Skill | v2 / 无 |
| find-non-living-thing | 236 | v3，6 条 Skill | v2 / 无 |
| grow-plant | 96 | v4d，10 条 Skill | v14b / shared-state-checkpoint-v1 |
| inclined-plane-determine-angle | 132 | v4d，10 条 Skill | v14b / shared-state-checkpoint-v1 |
| power-component | 18 | v4d，10 条 Skill | v14b / shared-state-checkpoint-v1 |

本机 ScienceWorld 1.2.3 的 `get_variations_test()` 已确认这些编号属于 test。检查只加载各类 train v000，未读取候选题内容。执行器在付费调用前再次核对官方列表和环境文件哈希。

这些是**已有任务类别中的未使用变体**，不是六种新任务。项目此前已依据这些类别的 train/dev 和部分 test 结果修改过 Skill。我们只能检验冻结实现对所选变体的表现，不能声称完全盲测或泛化到全部 ScienceWorld。每题内部三组共用 Agent 与控制器；不同类别沿用原有协议，跨类别差异不能归因于 Skill。

## 3. 冻结条件

| 条件 | 检索索引 | 给 Agent 的内容 |
|---|---|---|
| no_skill | 无 | 无 Skill |
| semantic_flat_retrieval | Name + Description | Top-3 完整 Skill，按检索顺序加载 |
| semantic_body_retrieval | 完整五字段 Skill | Top-3 完整 Skill，按检索顺序加载 |

语义编码器沿用本地 `all-MiniLM-L6-v2`，384 维、CPU、256-token 上限、归一化向量。超过长度就报错停止，不静默截断、不退回哈希检索。模型文件及依赖必须匹配已有离线基线。Gold 标签只作事后审计，不传给检索器。

LLM 请求名固定为 `deepseek-v4-flash`，temperature 0，thinking disabled，环境为 easy。沿用 smoke 的 **100 步**设置：Agent 最多记录 100 个工具动作，同时环境 `envStepLimit=100`；`wait` 可一次推进十个环境 move，所以两种计数不等价。环境包装器可能在 move 数大于 100 后才结束。`done=true` 不代表成功，成功只认环境 `score >= 100`。

每道题的条件顺序由种子 20260924 生成，并在三个 repeat 间轮换，使每组各占一次第一、第二、第三个位置。每个 repeat 的题目顺序另行固定洗牌。运行时不更换题号、Skill、模型、预算或判断标准。

## 4. 指标与分析规则

| 六项核心指标 | 计算口径 |
|---|---|
| Task Success Rate | 成功 episode 数 / 全部已完成 episode 数；正式表每组应有 18 条 |
| Input Tokens | 每个 episode 内所有 LLM 调用的输入 token 之和，再跨 episode 取平均；包含重复发送的历史和 Skill，不是单次上下文长度 |
| Output Tokens | 每个 episode 内所有 LLM 调用的输出 token 之和，再取平均 |
| Total Tokens | Input + Output；逐条核对相等，失败 episode 也纳入 |
| End-to-End Latency | 保留 `latency_ms`：环境对象建好之后的加载、重置、路由、推理与工具执行时间；本轮另存 `runner_ms`，包含环境创建和关闭，报告时并列注明，不混用 |
| Cost per Successful Task | 该条件全部完成 episode 的估算 API 费用之和 / 成功数；成功数为 0 则未定义 |

补充记录 Score、动作数、environment moves、路由时间、缓存命中/未命中 token、加载列表与提示哈希。路由时间包含每次 MiniLM 冷启动；本地模型耗时计入延迟，不计入 API 费用。费用使用冻结代码中的价格表，未独立核对平台账单，也未估算本地电费。不同条件缓存状态可能不同，费用与 token 不必同比例变化。

先对每道题三次重复取平均，再做六道题等权的配对比较。完整表保留六项指标，另列每次 repeat 的均值与标准差、逐题成功数和 token 差。**54 次运行只有六个任务变体，不能当成 54 道独立题。** 本轮以描述性结果判断是否值得扩大验证，不凭单个 p 值宣称方法成立，不在六题结果上调参后继续称确认。

必须同时报告两组检索的同集合率、同顺序率与同提示哈希率。提示相同的配对中，LLM 接受相同 Skill 干预；执行成本差只能描述为运行差异，不能解释为“正文检索让 Agent 更会做题”。若正文检索只更换干扰 Skill 或顺序，也照实列出。若六题均加载相同提示，结论写成“本轮未形成不同 Skill 干预，不能识别正文索引的执行收益”。不因这一结果临时加题或更换 Top-K。

## 5. 中断、费用与结果保存

原始文件为 `results/scienceworld_strong_confirm_6x3.jsonl`，不混入旧总账。唯一键为 `(task_name, variation, repeat, condition)`。运行器拒绝重复键、配置不一致和清单哈希不一致的续跑。模型失败、负分、步数耗尽都保留；完整 episode 一旦保存，续跑不重做。

累计已记录 API 估算费用到 **$0.50** 后，在下一个 episode 前暂停。一条 episode 可能越过阈值；这不是账户级硬额度。网络中断前尚未形成完整 episode 的消耗、其他终端调用都不在这笔账内。中途异常会停止程序；`--resume` 重跑未保存完整结果的键，因此中断 episode 可能重复花费。发生协议或数据错误时先检查，禁止删掉失败行择优重跑。

若触发费用暂停，保留部分结果并报告缺失数，不把不完整、不平衡的数据当成正式 54 条结果。不能偷偷上调阈值、替换题目后沿用同一冻结清单。该入口只支持单进程顺序运行，请勿同时开两个终端启动同一文件。

## 6. 运行命令

先进入项目，再检查预览。下面这一步不调用 API。

```bash
cd "/Users/Check/Desktop/桌面ing/skill测试"
.venv/scienceworld/bin/python scienceworld_strong_confirmation.py
.venv/scienceworld/bin/python scienceworld_strong_confirmation.py --check
```

提交代码与协议后，单独启动付费运行。不要修改固定参数；API key 通过当前终端的环境变量提供。

```bash
.venv/scienceworld/bin/python scienceworld_strong_confirmation.py --execute --resume
```

断网或手动中止后，原命令可续跑。查看已保存数量和六项核心汇总：

```bash
.venv/scienceworld/bin/python scienceworld_strong_confirmation.py --status
python3 summarize_results.py results/scienceworld_strong_confirm_6x3.jsonl --run-id scienceworld-strong-confirm-6x3 --deduplicate --repeat-stats
```

`--status` 应显示 `completed: 54`；汇总三组各 `episodes: 18`，每组 `episodes_per_repeat: [6, 6, 6]`。在此之前只看进度，不下结论。
