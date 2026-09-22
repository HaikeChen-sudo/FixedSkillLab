# ScienceWorld Procedure 单字段开发 pilot 预注册

日期：2026-09-22。状态：只完成本地预览和测试，尚未运行 DeepSeek episode。本 pilot 用两道重复使用过的 dev variation 检查实验链路与局部机制；研究结论不使用这四个 episode。

## 对照与任务

| 任务 | P0 | P1 |
|---|---|---|
| `chemistry-mix:v016` | v4 的 `chemistry-recipe-mix` | v4b 同名 Skill；给出 `read recipe`、`mix <container>` 的明确命令 |
| `inclined-plane-determine-angle:v084` | v4b 的 `measure-inclined-plane-angle` | 仅重写第三步，要求比较两次测得的时间再选斜面 |

每个任务只加载一条人工 Gold Skill。`scienceworld_procedure_pilot.py` 在同一 `oracle_v4` Agent 调用期间临时替换这条 Skill，调用结束就恢复。脚本逐字段检查：每组 P0/P1 只有 `procedure` 不同。两组共用 `scienceworld-v14b` 系统提示、`shared-state-checkpoint-v1` 控制器、工具接口与环境配置。Skill Prompt 的 SHA-256 随 episode 入库。

## 固定运行参数

- 模型 `deepseek-v4-flash`，temperature 0，`easy` simplification。
- 两道任务各跑 P0 和 P1 一次，共 4 个 episode。顺序种子 `20260922`；脚本预览显示：化学 P1→P0，斜面 P0→P1。
- 每个 episode 最多 100 次 Agent 工具调用。累计**已记录**费用达到 0.05 美元时，脚本不启动下一个 episode。它无法中途截断正在运行的 episode；网络异常前已发生但未记录的费用也不计入阈值。
- 运行前使用 `python3 scienceworld_procedure_pilot.py` 查看顺序与 Prompt 哈希。实际运行需要显式加 `--execute --run-id <唯一名称>`；断线后只用相同 run-id 加 `--resume`。恢复检查模型、温度、步数、顺序种子、suite 与 Prompt 哈希。运行期间不编辑 Agent 或 Skill 文件。

## 读数与停机规则

成功只取 ScienceWorld 的最终环境分数 100。次要读数取 Input Tokens、Output Tokens、Total Tokens、时延、费用、工具调用及动作序列。化学题检查有效读配方→使分数上升的混合→最终聚焦，并单独数无效混合。斜面题检查聚焦前是否在两块斜面放置木块、读取计时器且达到环境 50 分测量里程碑，再区分过早聚焦与达到里程碑后选错。两次计时器读数本身不能证明测量有效。

若字段比较、Prompt 哈希或共享协议检查失败，不启动后续 episode。若模型调用报错，保留已写记录；先查明错误，再决定是否用同一配置恢复。费用阈值触发后停止，不为凑满 4 条临时提高阈值。

四条记录即使全成功，也只能说明配对运行器可用。P0/P1 的文字长度不同；任何成功率或成本差异都不足以证明 Procedure 有普遍效果，更不能证明论文新颖性。下一次设计独立确认时，需加入未用过的 variation、重复运行和长度对照，并冻结代码版本。
