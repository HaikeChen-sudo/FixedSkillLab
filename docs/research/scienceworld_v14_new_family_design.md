# ScienceWorld v14：新任务类型的预注册设计草案

日期：2026-09-19。状态：**选题已固定，实验尚未预注册完成，也尚未运行 DeepSeek**。正式预注册要等新 Skill、路由器与运行代码写好并记录哈希；本文件不能冒充已锁定的实验协议。机器可读的题目和规则见 [设计清单](scienceworld_v14_new_family_design.json)。

## 研究问题

现有 ScienceWorld 正结果来自同六类任务的不同 variation。v14 检查：给此前没有参加实验的任务类型人工编写固定 Skill 后，Body-aware Retrieval 相对 No Skill 能否同时提高客观成功率、减少模型 Token？这检验**方法在新任务类型上的适用性**，不是旧 Skill 对新任务的零样本迁移。若结果不支持，就把 v11b 的收益限定在旧套件，不继续改 test 题上的 Skill。

## 题目与来源

从已安装的 ScienceWorld 1.2.3 中选出四个此前未纳入本项目 API 实验的任务类型。选择时只查看任务名、官方 variation 划分和 train/dev 的环境标准路径；未看 test 题目文本或解题轨迹。四类分别覆盖电路、植物、化学和斜面测量。每类取官方 test 列表的前三个 variation，不按模型表现换题。

| 任务类型 | train / dev / test 数量 | 开发检查用的 train、dev variation | 正式 test variation |
|---|---:|---|---|
| `power-component` | 10 / 5 / 5 | 0、10 | 15、16、17 |
| `grow-plant` | 62 / 31 / 33 | 0、62 | 93、94、95 |
| `chemistry-mix` | 16 / 8 / 8 | 0、16 | 24、25、26 |
| `inclined-plane-determine-angle` | 84 / 42 / 42 | 0、84 | 126、127、128 |

本地标准路径验收在上述八个 train/dev variation 上均达到环境分数 100；动作数依次为电路 8/10、种植 29/41、化学 20/15、斜面 54/55。这只证明环境任务在 400 步预算内可解，不代表 Agent 会成功。正式 test 的 Gold 路径要等 Skill 和代码冻结后再验收；验收结果若不合格，公开作废当前版本，不暗中删题或替换。

## 干预与执行顺序

保持同一个 `deepseek-v4-flash` 请求名、temperature 0、ScienceWorld `easy`、400 环境步、同一 Agent 系统提示与动作工具。唯一实验变量是 Skill 加载方式：

| 条件 | 加载内容 | 作用 |
|---|---|---|
| `no_skill` | 不加载 Skill | 基线 |
| `flat_retrieval` | 名称与描述索引 Top-3，加载完整 Skill | 检索对照 |
| `body_aware_retrieval` | 完整正文索引 Top-3，加载完整 Skill | 主干预 |
| `oracle_v4` | 直接加载人工对应的新 Skill | 区分 Skill 内容与路由问题的上界对照 |

新库由旧 v3 六条 Skill 加四条新 Skill 组成；旧 Skill 原文不改。新 Skill 使用同一五字段格式：Name、Description、Activation Condition、Procedure、Termination Condition。只能看 train 题及 dev Pilot 来写和修改。Flat 与 Body-aware 对**同一十条 Skill**做 Top-3 检索，并加载同一版本的正文；二者只差索引字段。Oracle 标签在看 test 结果前人工固定。不能依据 test 的路由排名、失败轨迹或成功率回写 Skill。

开发阶段先对四个 dev variation 各跑四条件一次，共 16 个 episode；这批数据只用于调试与写 Skill，不进入正式统计。随后冻结代码、Skill 文本、Gold 标签、检索器、模型参数及本清单的哈希。冻结后对十二个 test variation 做离线 split 验证与 Gold 路径验收，保存结果，再运行正式实验：12 题 × 4 条件 × 3 次 = **144 个 episode**。每道题每个 repeat 内随机排列四条件，固定随机种子 0。API 中断后只按唯一键补跑缺失 episode，不重跑已有结果以择优。

现有 `scienceworld_experiment.py` 只支持旧六类任务，`oracle_v4` 和十条 Skill 库也尚未实现。因此**现在不能直接执行 v14 正式命令**。实现后先跑单元测试和 dev Pilot，再生成带代码、Skill、检索器 SHA-256 的最终预注册 manifest，提交 Git；只有这些完成后才能调用 test API。正式运行由用户另行启动，不在本阶段自动调用。

## 预定指标和判定

成功只由环境分数 `score >= 100` 判定。每个条件报告六项核心指标：Task Success Rate、平均 Input Tokens、平均 Output Tokens、平均 Total Tokens、平均 End-to-End Latency、Cost per Successful Task。成本按**该条件所有 episode 的 API 成本之和 ÷ 成功 episode 数**计算；若无成功则记为未定义。另报告平均环境动作数、平均分数、Router Gold Hit@3 及逐题轨迹。

主比较为 Body-aware − No Skill。先对同一 task-variation 的三次重复取平均，再按十二道题等权计算差值；不能把 36 次重复当成 36 道独立题。主终点为成功率差与平均 Total Tokens 差。预定“质量与计算成本双收益”的判据是：两个差值的双侧 95% 任务簇 Bootstrap 区间分别完全大于 0、完全小于 0。重抽样在四个任务类型内各抽三个 task-variation，10,000 次，随机种子 20260919。两项主终点同时满足才用“双收益”；只满足一项则分别报告成功率或 Token 收益，不把探索性差值写成确认结论。区间及判据是操作规则，四个任务类型仍不足以推断到 ScienceWorld 所有任务类型。

Flat 对 No Skill、Body-aware 对 Flat 及 Oracle 对 Body-aware 均为次要比较。逐类报告方向，尤其核查是否只靠一类长轨迹拉低 Token 均值；同时报告中位数和各题配对差。若 test 题全部接近成功率天花板，成功率分析如实保留，不能事后按 No Skill 失败筛题。未解决的 API 传输错误不算 episode，原键续跑；已完成但模型停机、用尽步数或动作无效的 episode 保留并按环境分数计分。任何 test 后的 Skill 或代码修改都必须开新版本，v14 结果不能混合。

## 冻结前检查

1. 新 Skill 与十条库的加载、四条件选取、Top-3、Gold 标签和任务清单都有本地测试；No Skill 不加载 Skill。
2. dev Pilot 四条件各 4 条记录，Token 账本满足 `Total = Input + Output`，没有重复键；记录 dev 的用途，不把 Pilot 写成验证。
3. 最终 manifest 记录 Skill/Agent/检索器哈希、Python 包版本、运行参数和十二道 test 题；先提交协议，再做 test split 与 Gold 检查，再启动模型实验。
4. test Gold 若不满 100、官方 split 不符或协议实现不一致，停止；公开原因与新版本。不得只替换出问题的题继续使用同一预注册编号。

这一步只完成了选题和分析规则。Skill 实现、dev Pilot、最终哈希冻结及正式 API 评估仍待完成。
