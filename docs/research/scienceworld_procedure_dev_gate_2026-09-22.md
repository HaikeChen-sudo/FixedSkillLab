# ScienceWorld Procedure 单字段：无 API 开发集门检

2026-09-22。只使用 `chemistry-mix:v016`、`inclined-plane-determine-angle:v084` 两道官方 dev variation、现有 Skill 文本与既有轨迹。本文件登记文本干预和客观判定规则；没有运行新 Agent episode，也不把开发题当独立确认。

## 要识别的效应

同一道任务、同一 Agent 提示与控制器、同一模型和环境设置下，直接加载同一条人工 Gold Skill，只改变它的 **Procedure**。Name、Description、Activation Condition、Termination Condition、其余 Skill 和工具接口保持逐字相同。先用 Oracle 加载，以免正文修改同时改变 Body-aware 的检索排名。比较任务成功、动作顺序和实际 Token；该比较只能识别所写 Procedure 文本的局部效应，不能代表所有 Skill 的 Procedure 字段。

## 事前登记的两组文本

| Dev 任务 | P0 | P1 | 固定项 |
|---|---|---|---|
| `chemistry-mix:v016` | `v4` 的 `chemistry-recipe-mix` Procedure：先找并读配方，再装入原料，混合后聚焦产物。 | `v4b` 同名 Skill 的 Procedure：明确 `read recipe` 与 `mix <container>` 命令，并禁止把配方、原料或容器当最终产物。 | 本地字段比较确认 `v4→v4b` 只改了这条 Skill 的 Procedure；未来 P0/P1 运行必须共用同一 Agent 版本，不能直接对比已有 v14 与 v14b 成功率。 |
| `inclined-plane-determine-angle:v084` | 当前 `measure-inclined-plane-angle` 的四步 Procedure；第三步明确“同一木块在较浅斜面上耗时更长”。 | 保留第一、二、四步；仅把第三步改为：`Repeat the same experiment on the second plane. With the same block, compare the two measured travel times before selecting a plane.` | Name、Description、Activation、Termination 与其余三步逐字相同。P1 是待审的开发文本，尚未写入正式 Skill 库。 |

P0/P1 的词数和模型 Token 数不完全相等。若开发 pilot 出现差异，正式实验还需等长无关 Procedure 对照，不能把长度、措辞与信息量的影响混为一谈。

## 从环境日志判定，不问模型理由

| 任务 | 预定事件与错误 | 已有 dev 轨迹能否识别 |
|---|---|---|
| 化学 | `read` 类配方动作必须先于第一次使分数上升的 `mix`；有效 `mix` 应先于最终 `focus`。单独计数分数未上升的 `mix` 尝试，避免把一次无效命令误记为完成混合。最终成功只认环境分数 100。 | 能。v14b 四条件都出现读配方、有效混合和聚焦产物；No Skill 还出现一次未推进分数的混合尝试。四条件均成功，因此这些轨迹只验证规则可读，不提供 P0/P1 效应。 |
| 斜面 | 第一次 `focus` 前，两块不同斜面都应有放置木块与计时器读数；若尚未完成两次测量就聚焦，标为过早决策。聚焦后的环境分数 100／-100 判定选对／选错；把“完成测量后仍选错”与“未测量就聚焦”分开。 | 能。v14b No Skill 在未测量时聚焦，得 -100；Oracle 完成测量后仍聚焦错误斜面，得 -100；Flat 和 Body-aware 完成测量并得 100。既有条件同时改变加载方式，不能归因于 Procedure。 |

这些规则只依赖 `trace[].command`、环境 observation、score 与 done；模型生成的解释、最终文字均不参与评分。测量前提以动作序列判断，不能仅靠最终分数反推。

## 门检结论与下一关

**可观测性过门，因果与新颖性没有过门。** 两类 dev 任务都有可从日志直接识别的前置步骤和错误类型；`v4→v4b` 又提供一组真实的 Procedure-only 文本差异。现有轨迹来自不同加载条件，且 v14→v14b 同时改了 Agent 提示／控制器，不能据此声称 Procedure 提高成功率。

下一步若要运行付费开发 pilot，先做四项检查：给斜面 P1 文本做字段级 diff；让同一 Agent／控制器在 P0/P1 共用；把上述事件规则实现为读取现有 JSONL 的确定性检查并人工复核至少两条轨迹；在 dev-only 运行前登记任务、条件顺序、重复数、步数上限及停机成本阈值。任一项未满足就不运行。即使 pilot 有差异，也只能决定是否继续研究；[停／走判定](fixed_skill_novelty_go_no_go_2026-09-22.md)仍标记 Procedure 为 `explore`，论文创新性尚未成立。
