# T 型 Agent Skill 结构：可计算定义与最小验证方案

## 结论先行

“T 型”不应指一条很长的 Skill，也不应只是把通用 Skill 和专业 Skill 放进同一文件夹。适合研究的对象是 **Agent 的 Skill 组合结构**：

- 横向层提供跨任务族复用的执行原则或确定性控制；
- 纵向层在一个目标领域内提供逐级具体化的 Procedure；
- 路由器先保留横向层，再只加载与当前任务匹配的一条纵向路径。

因此，建议把概念命名为 **T-shaped Skill Portfolio（T 型 Skill 组合）** 或 **T-Skill Architecture**，不要声称“每一条 Skill 都是 T 型”。

当前 FixedSkillLab 已经证明两件事：Body-aware Retrieval 在一组 ScienceWorld 任务上优于 No Skill；完整 Procedure 在定向状态转换任务上优于 Metadata 和等词数 Placebo。下一步可以研究一个更窄的问题：

> 在固定模型、工具和任务下，“跨任务优化层 + 单领域深层 Procedure 路径”是否比单独使用横向层或纵向 Skill 更有效？

这个问题能被实验否定，也能直接接入现有 ScienceWorld 代码。

## 1. 概念来源与迁移边界

T 型人才的稳定含义是“广度与深度并存”。Hansen 与 von Oetinger 在 2001 年讨论 T-shaped managers 时，把横向部分解释为跨组织单元共享知识，把纵向部分解释为对本业务单元保持深入投入。Demirkan 与 Spohrer 后来把 T-shaped professionals 概括为专业深度与知识、经验、沟通等广度的结合。两者讨论的是人和组织，不是 Agent 数据结构。[Hansen & von Oetinger, 2001, Harvard Business Review](https://hbr.org/2001/03/introducing-t-shaped-managers-knowledge-managements-next-generation)；[Demirkan & Spohrer, 2018, Service Science](https://doi.org/10.1287/serv.2017.0204)；[IBM Research publication page](https://research.ibm.com/publications/cultivating-t-shaped-professionals-in-the-era-of-digital-transformation)

这里的 T 型 Agent Skill 是一个新的操作化定义，不是从人才研究中直接推导出的既有算法。人才文献只提供两个设计约束：

1. 横向部分必须真的跨多个任务族复用；
2. 纵向部分必须在一个领域内达到明显高于其他领域的程序深度。

如果所有任务都各有一条同样详细的 Skill，那是均匀的专业 Skill 库，不是 T 型。如果只有一条状态转换 Procedure，没有跨任务通用层，那是 I 型专长。

本轮检索未发现把 LLM Agent Skill Library 明确定义为“横向广度层 + 纵向深度层”，并把两者交互作为实验变量的论文。现有工作分别研究 Skill 表示、检索或一般层次图。这里可能有研究空位，但是否构成方法创新，要由受控实验而不是命名决定。

## 2. 可计算定义

### 2.1 数据结构

T1 把横向层限制为 Skill 文本。T2 放宽为跨任务优化层：横向部分可以包含固定 Skill 文本和确定性执行控制器，但不得读取任务族标签后注入专用解法。T2 的分数型重复动作拦截器产生了负交互，没有通过预注册门槛。T3 移除横向 Skill 文本，只保留一个不使用任务族标签的状态感知控制器，使 Full 和 Vertical 的 Procedure 文本完全相同。纵向部分仍是任务领域 Procedure。

令任务族集合为 \(\mathcal D=\{d_1,\ldots,d_m\}\)。每条 Skill 记为：

\[
s=(id, role, scope, domain, level, parent, activation, procedure, termination)
\]

字段含义：

| 字段 | 允许值或含义 |
|---|---|
| `role` | `horizontal` 或 `vertical` |
| `scope` | 该 Skill 适用的任务族集合 |
| `domain` | 纵向 Skill 所属领域；横向 Skill 为空 |
| `level` | 具体化层级，横向层为 0，纵向路径从 1 递增 |
| `parent` | 上一级 Skill；用于形成一条可验证的路径 |
| `activation` | 客观或可审计的触发条件 |
| `procedure` | 执行步骤 |
| `termination` | 终止条件 |

横向集合 \(H\) 中的 Skill 覆盖多个任务族。目标领域 \(d^*\) 的纵向集合构成一条路径：

\[
V_{d^*}=(v_1 \rightarrow v_2 \rightarrow \cdots \rightarrow v_L)
\]

其中层级越深，Procedure 越具体。对任务 \(x\)，T 型加载规则是：

\[
R_T(x)=H_x \cup \operatorname{Path}(v_1,v_{leaf(x)})
\]

非目标领域任务只加载匹配的横向 Skill；目标领域任务加载横向 Skill 和一条纵向路径。不要把所有纵向分支同时塞给模型。

一个可直接序列化的例子：

```json
{
  "id": "state-change-freeze",
  "role": "vertical",
  "scope": ["freeze", "change-the-state-of-matter-of"],
  "domain": "state-change",
  "level": 3,
  "parent": "state-change-cooling",
  "activation": "The task requires a named sample to become solid.",
  "procedure": ["..."],
  "termination": "Environment score reaches 100 or done is true."
}
```

### 2.2 结构指标

不建议只报一个人为拼接的 “T-score”。至少冻结并报告四个结构量：

\[
B=\frac{|\bigcup_{h\in H}scope(h)|}{m}
\]

\(B\) 是横向覆盖率。

\[
D=\max_{d}\operatorname{LongestPath}(V_d)
\]

\(D\) 是最大纵向深度。

\[
C=\frac{D_{d^*}}{\sum_d D_d+\epsilon}
\]

\(C\) 是深度集中度，用于排除“每个领域都同样深”的均匀层次库。

\[
I=\frac{|\{v\in V_{d^*}:v\text{ 可由横向层到达}\}|}{|V_{d^*}|}
\]

\(I\) 是横向层与纵向层的连通比例。

第一版可以预注册：\(B\ge 0.5\)、\(D\ge 2\)、\(C\ge 0.5\)、\(I=1\)。这些阈值只是结构验收标准，不能根据实验结果回调。

## 3. 与现有 Skill 组织方法的区别

| 结构 | 存储关系 | 推理时加载 | 研究重点 |
|---|---|---|---|
| Flat Skill Library | Skill 彼此独立 | Top-k 独立 Skill | 检索是否找对 |
| T-shaped Portfolio | 通用横向层 + 一个领域纵向路径 | 横向骨架 + 一条匹配路径 | 广度、深度及其组合是否互补 |
| Hierarchical Skill Graph | Skill、原子操作和多种有类型边组成一般图 | 任务相关子图，运行中切换节点 | 分解、转移、兼容、恢复和动作落地 |

Skill-Pro 把可执行 Skill 定义为 Activation、Execution 和 Termination 三部分，并把它们放进可选择、可维护的 Skill Pool。它与本项目的固定 Skill 格式直接对应，但其自动演化和 Non-Parametric PPO 不属于 T 型结构的第一轮实验。[Skill-Pro, ICML 2026 Spotlight](https://arxiv.org/abs/2602.01869)；[official code](https://github.com/Miracle1207/Skill-Pro)

SkillRouter 把大规模 Skill 系统明确为路由问题，并报告隐藏 Skill body 会显著降低检索准确率。这支持当前项目继续记录 body-aware routing，但它解决的是“选哪条 Skill”，不是“Skill 组合应呈什么形状”。该论文目前是 arXiv 预印本。[SkillRouter, arXiv:2603.22455](https://arxiv.org/abs/2603.22455)

HiSkill 使用 Skill 节点、AtomicOp 节点和分解、时序、兼容、支持、恢复等有类型边，推理时检索子图并根据任务状态切换 Skill。T 型结构比它受限得多：只有横向骨架和一个主要纵向领域，不需要任意关系图或运行中图搜索。该论文目前是 arXiv 预印本；论文链接的官方 GitHub 仓库在 2026-09-16 仍为空，不能把“代码已开源”当作已核验事实。[HiSkill, arXiv:2607.25853](https://arxiv.org/abs/2607.25853)；[authors' repository](https://github.com/BUPT-GAMMA/HiSkill)

一句话区分：**Flat 研究集合，Hierarchy 研究一般关系图，T-shaped 研究受约束的广度—深度分配。**

## 4. 可证伪假设

### H1：横向迁移

在非纵向领域任务上，Horizontal-only 的成功率高于 No Skill，且平均 Total Tokens 或 Environment Moves 不增加。

否定条件：横向层在广度任务上没有收益，或收益完全来自更长预算。此时它只是通用提示，不足以构成有效的横向能力。

### H2：纵向专长

在目标领域任务上，Vertical-only 的成功率或平均 Score 高于 No Skill。

否定条件：纵向路径对目标领域无效。此时 T 型结构没有“竖杠”。

### H3：组合互补

在目标领域上定义交互效应：

\[
\Delta_{int}=(SR_{H+V}-SR_V)-(SR_H-SR_N)
\]

其中 \(N\) 为 No Skill，\(H\) 为 Horizontal-only，\(V\) 为 Vertical-only，\(H+V\) 为 T-full。

主假设是 \(\Delta_{int}>0\)，并且 T-full 的成功率高于 \(\max(SR_H,SR_V)\)。

否定条件：T-full 不优于 Vertical-only。那只能说明纵向 Skill 有效，不能说明 T 型整合有效。

### H4：受控结构收益

在 Skill body 和提示 Token 近似匹配时，T-typed 优于 Flat-matched。T-typed 明示 `role`、`level`、`parent` 和加载顺序；Flat-matched 保留相同 Procedure 句子，但不提供横向/纵向关系。

否定条件：Flat-matched 同样好或更好。此时关系标注和 T 型加载策略没有增量价值，结果应解释为 Skill 内容收益。

### H5：领域内迁移

只用 `boil`、`melt`、`freeze` 编写纵向层，在未参与编写的 `change-the-state-of-matter-of` 或熔点测量任务族上测试。

否定条件：收益只出现在编写 Skill 时见过的任务族或 variation。那更像任务模板记忆，不是领域专长。

## 5. 适合 FixedSkillLab 的最小实验

### 5.1 第一轮只做 2×2 因子实验

先不用 Router，人工 Oracle 加载，避免把“结构效果”和“检索错误”混在一起。

| Condition | 横向层 | 纵向路径 | 作用 |
|---|---:|---:|---|
| `no_skill` | 否 | 否 | 基线 |
| `t_horizontal` | 是 | 否 | 测广度 |
| `t_vertical` | 否 | 是 | 测深度 |
| `t_full` | 是 | 是 | 测组合及交互 |

如果这四组没有形成信号，不要增加图路由、自动学习或更多 Skill。

### 5.2 Skill 内容

横向层只写跨任务执行规则，不写具体任务答案：

1. 保存完整 object referent，避免同名对象漂移；
2. 在不可逆 `focus` 前检查目标身份；
3. 每次动作后读取 observation、score 和 done；
4. 连续两次无进展时检查 inventory、位置、容器状态和前置条件；
5. 达到环境成功条件才终止。

纵向层选 `state-change`，复用现有 v3 Procedure，拆成三层：

| Level | 内容 | 示例 |
|---|---|---|
| V1 | 状态转换共性 | 保持样本身份、检查初始物态、识别中间态 |
| V2 | 过程类别 | heating 或 cooling 的设备选择、等待与测量策略 |
| V3 | 任务叶子 | boil、melt、freeze 的终止和恢复规则 |

这比新写一套大 Skill 库省事，也能继承 v13b 已验证的 Procedure。

### 5.3 任务组成

Pilot 可以用 12 个 case：

- 6 个纵向领域 case：`boil`、`melt`、`freeze` 各 2 个；
- 6 个横向广度 case：`use-thermometer`、`find-living-thing`、`find-non-living-thing` 各 2 个。

规模为：

\[
12\ tasks\times4\ conditions\times1\ repeat=48\ episodes
\]

Pilot 只查实现、加载记录和效应方向，不下结论。由于现有状态转换 test variations 已被多轮实验使用，正式确认应改用预先冻结的新任务族，例如 `change-the-state-of-matter-of`，或更换尚未用于 Skill 编写的 ScienceWorld task/variation。ScienceWorld 官方环境提供任务名、variation、score、moves 和 train/dev/test variation 接口，适合继续使用客观评分。[ScienceWorld EMNLP paper](https://aclanthology.org/2022.emnlp-main.775/)；[official repository](https://github.com/allenai/ScienceWorld)；[Python environment API](https://github.com/allenai/ScienceWorld/blob/main/scienceworld/scienceworld.py)

### 5.4 记录字段

沿用现有 episode JSONL，再增加：

```json
{
  "skill_architecture": "t_shaped",
  "horizontal_skills_loaded": ["scienceworld-execution-control"],
  "vertical_domain": "state-change",
  "vertical_path": ["state-change", "heating", "boil"],
  "vertical_depth": 3,
  "skill_prompt_words": 412,
  "skill_prompt_characters": 2870,
  "structure_version": "t1"
}
```

DeepSeek API 不返回 Skill 子串的独立 token 数，不能伪造精确值。T1 单独记录可复算的 `skill_prompt_words` 和 `skill_prompt_characters`；完整输入 token 继续使用 API 返回的 `input_tokens`。这样至少能区分 Skill 本身变长与执行轮数增加。

### 5.5 指标与统计单位

主指标：Task Success Rate。

次指标：Average Score、Input/Output/Total Tokens、End-to-End Latency、Cost per Successful Task、Tool Calls、Environment Moves。

机制指标：错误 `focus` 次数、重复无效动作、无进展循环、预算耗尽、样本身份切换。

每个 task variation 是统计簇，三次 repeat 不是三个独立任务。正式实验继续使用按 variation 聚类的 Bootstrap，并报告 2×2 的 \(\Delta_{int}\)。成功率配对检验可以保留 McNemar，但不能只报 episode 级 p 值。

## 6. 建议的研究顺序

1. **T1：Oracle 2×2 Pilot。** 48 episodes，确认横向和纵向内容确实按预期加载。
2. **T2：分数型重复动作控制。** 开发诊断已完成，Full 4/6，Vertical 5/6，未通过门槛。
3. **T3：状态感知检查点。** 在相同两个开发 case 上进行最后一次横向层调整；如果 Full 仍不优于 Vertical，停止在该任务集上继续调参。
4. **Flat-matched Control。** 只在 T3 通过后才做，固定 Skill body 与 Token 预算，移除 `role/level/parent` 和路径加载规则。
5. **Router 与跨模型复现。** 只在 T 结构已有 held-out 信号后展开。

不建议现在加入自动生成 Skill、PPO 或完整 Skill graph。它们会同时改变 Skill 内容、结构和选择机制，T 型假设反而无法检验。

## 7. 什么结果才算支持 T 型结构

仅有 `t_full > no_skill` 不够。最低证据链应同时满足：

- 横向层在非目标领域有可重复收益；
- 纵向层在目标领域有可重复收益；
- T-full 高于 Horizontal-only 和 Vertical-only，交互效应方向为正；
- 对等内容或等 Token 的 Flat-matched 仍保留差异；
- 至少一个未参与 Skill 编写的相关任务族出现迁移收益。

如果只有第三项之前的部分成立，论文应写成“通用规则与领域 Procedure 的组合实验”，不要把结果包装成已证明的 T 型架构。

## 8. 当前最值得做的版本

我建议把下一版定为 **ScienceWorld T1：Oracle T-shaped 2×2 Pilot**。它只新增一个横向 Skill、一个纵向层级描述和四个条件，不改模型，不改工具，不加学习。预计 48 episodes，成本和运行时间都可控。

T1 的成败判断很简单：

- 若 Horizontal-only 在广度任务上没有改善，先重写横向 Skill；
- 若 Vertical-only 在状态转换任务上没有改善，说明拆层破坏了 v13b Procedure；
- 若两者分别有效但 T-full 没有额外收益，T 型组合假设失败；
- 若三项都成立，再做新任务族上的正式确认和 Flat-matched 对照。

这条路线把“T 型”从比喻变成了一个有字段、有加载函数、有交互效应、也可能被否定的实验对象。

## 一手来源

1. Morten T. Hansen, Bolko von Oetinger. [Introducing T-Shaped Managers: Knowledge Management's Next Generation](https://hbr.org/2001/03/introducing-t-shaped-managers-knowledge-managements-next-generation). *Harvard Business Review*, 2001.
2. Haluk Demirkan, James C. Spohrer. [Cultivating T-Shaped Professionals in the Era of Digital Transformation](https://doi.org/10.1287/serv.2017.0204). *Service Science*, 2018. [IBM Research 页面](https://research.ibm.com/publications/cultivating-t-shaped-professionals-in-the-era-of-digital-transformation).
3. Qirui Mi et al. [Skill-Pro: Learning Reusable Skills from Experience via Non-Parametric PPO for LLM Agents](https://arxiv.org/abs/2602.01869). ICML 2026 Spotlight. [官方代码](https://github.com/Miracle1207/Skill-Pro).
4. Yanzhao Zheng et al. [SkillRouter: Skill Routing for LLM Agents at Scale](https://arxiv.org/abs/2603.22455). arXiv preprint, 2026.
5. Yu Hao et al. [HiSkill: Empowering LLM Agents with Hierarchical Skill Graphs](https://arxiv.org/abs/2607.25853). arXiv preprint, 2026.
6. Ruoyao Wang et al. [ScienceWorld: Is Your Agent Smarter than a 5th Grader?](https://aclanthology.org/2022.emnlp-main.775/). EMNLP 2022. [官方代码](https://github.com/allenai/ScienceWorld).
