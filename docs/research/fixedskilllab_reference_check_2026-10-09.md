# 中文初稿相关工作核查

核查日期：2026-10-09。范围限定为五篇既有参考文献。逐一使用网络工具打开 arXiv 摘要页、版本记录和指定 v1 HTML，再检查下列论断所在段落；没有把旧笔记当作外部验证。五篇均可访问，题名和版本匹配。此记录只验证原文写了什么，不代表独立复现其结果，也不是系统综述。

## 可写入正文的表述

### 1. Skill Following

题名：*Skill Following: Evaluating Actual Skill Use in Retrieval-Enabled LLM Agents*。作者：Seonghyeon Cho、Chanjun Park。核查版本 v1，提交日期 2026-09-01；摘要页仅列该版本。[版本记录](https://arxiv.org/abs/2609.00549)

已验证：论文以同任务的 Skill 启用／禁用执行构成配对，区分整体效果与发生检索的任务子集；§4.4 还列出空返回、无信息填充、随机 Skill 和破坏内容等对照。可引用为：“Skill Following 使用同任务配对和内容对照检查检索后的实际收益，说明检索发生与任务受益需要分开测量。”[v1 §3、§4.3–4.4](https://arxiv.org/html/2609.00549v1)

边界：该协议不是逐字相同加载提示的 Flat／Body 对照。本文不将按检索事件筛选的指标自动解释为检索或服从度的因果中介效应。

### 2. SkillSeek

题名：*SkillSeek: Revisiting Agent Skill Retrieval at Marketplace Scale*。作者：Guanqun Yang、Wenlong Zhang、Tian Shi、Ping Wang。核查版本 v1，提交日期 2026-09-30；摘要页仅列该版本。[版本记录](https://arxiv.org/abs/2609.38822)

已验证：§3.1 使用 BGE-base 双编码器和交叉编码器重排；§4.2 比较 BM25、两阶段检索和 LLM 介入的检索循环。可引用为：“SkillSeek 在 SkillsBench 与 OpenHands 设置下报告了传统信息检索方法的竞争力，为 Skill 检索研究纳入 BM25 和两阶段强基线提供了直接先例。”[v1 §3.1、§4.2](https://arxiv.org/html/2609.38822v1)

边界：默认索引还包含离线生成的 Tool-REX 标签，不是本项目的单纯 Name／Description 索引。不能用其结果直接证明本项目 Flat 与 Body 等价，或宣称所有设置均不需要 LLM 检索。

### 3. SkillApt

题名：*SkillApt: Learning When to Activate Agent Skills from Counterfactual Evidence*。作者：Shuang Guo。核查版本 v1，提交日期 2026-09-22；摘要页仅列该版本。[版本记录](https://arxiv.org/abs/2609.26863)

已验证：§3.2 以匹配的 WITH／WITHOUT 执行建立历史证据，§3.5 将候选 Skill 的 LOAD／ABSTAIN 与工具、验证器前置条件失效后的 Quarantine 分开。可引用为：“SkillApt 将检索与是否加载分成两次决策，用历史配对执行证据估计候选 Skill 在当前状态下是否值得启用。”[v1 §3.1–3.5](https://arxiv.org/html/2609.26863v1)

边界：v1 的 SRA 状态表示来自题目文本，估计目标只编码正确性关系；成本标签被保留用于评估。不要将其概括成已实现任意环境状态或剩余动作预算控制器。此次未核查代码复现。

### 4. Agent Skills Can Be Harmful

题名：*Agent Skills Can Be Harmful: An Empirical Study of Skill-Induced Failures in LLM Agents*。作者：Gen Dong、Yanjie Gao、Liqun Li、Tianyin Xu、Yu Hua、Fan Yang。核查版本 v1，提交日期 2026-08-12；摘要页仅列该版本。[版本记录](https://arxiv.org/abs/2608.11888)

已验证：摘要说明对照同任务的无 Skill 或语义匹配 Skill 运行，§V 区分上下文膨胀、过量流程和依赖处理等效率退化来源。可引用为：“Agent Skills Can Be Harmful 分析了 Skill 引发的失败与成本退化，并指出额外执行流程不能仅用输入文本长度解释。”[v1 摘要、§V](https://arxiv.org/html/2608.11888v1)

边界：这是该文所研究数据中的归因分析，不是本项目同提示差异的原因证明，也不能推出所有 Skill 都有害。

### 5. SRA-Bench / SR-Agents

论文正式题名：*Skill Retrieval Augmentation for Agentic AI*。作者：Weihang Su 等。正文证据核查 v1，提交日期 2026-04-27；当前摘要页显示 v2 为 2026-05-21、v3 为 2026-06-07。参考文献应指定 v1，不把当前摘要的版本标记移到 v1 正文。[版本记录](https://arxiv.org/abs/2604.24594)

已验证：v1 §5.2 在 Gold Skill 始终位于候选中的设置下增加 hard-negative 干扰项、打乱候选顺序，并比较全文注入与渐进披露。可引用为：“SRA-Bench 在受控候选集合中分别考察检索噪声与 Skill 暴露方式，说明检索命中与实际加载不是同一个实验变量。”[v1 §5.1–5.2](https://arxiv.org/html/2604.24594v1)

边界：它不等于本项目逐字加载文本分组，也不能为本项目的分组差异提供因果识别。

## 状态与使用限制

五篇的上述窄论断均为“元数据和对应原文段落已核查”，没有不可访问项，也没有以仅匹配题名代替具体论断验证的项目。未核查完整代码、数据或复现实验；正文不得写成已独立复现。

这些文献足以否定“检索不等于使用”“相关不等于应加载”“Skill 会增加流程成本”等宽泛命题的首创性。本项目可报告本地证据如何限制结论，不据此宣称新算法或全网唯一发现。
