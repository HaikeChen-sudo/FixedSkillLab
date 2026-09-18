# FixedSkillLab Language

本文件固定实验中的核心术语，避免把 Skill 内容、结构和检索机制混为一谈。

## Language

**Fixed Skill（固定 Skill）**:
实验前由人工写定、运行期间不学习也不修改的行为指导单元。
_Avoid_: 自动经验、在线策略

**Horizontal Layer（横向层）**:
跨任务族复用的优化层，可以是固定 Skill 文本或确定性执行控制，但不能编码某个任务族的专用解法。
_Avoid_: 横向 Prompt、浅层 Skill

**Horizontal Skill（横向 Skill）**:
横向层中的文本指导单元，不等同于整个横向层。
_Avoid_: 横向控制器、完整横向层

**Vertical Skill（纵向 Skill）**:
针对一个任务领域或任务叶子的专用 Procedure。
_Avoid_: 专家 Prompt、深层 Prompt

**Vertical Path（纵向路径）**:
从领域到过程类别再到任务叶子的固定层级标签。它是实验结构，不是自动学习的 Skill graph。
_Avoid_: 动态图、检索链

**T-shaped Skill Portfolio（T 型 Skill 组合）**:
一个横向层与一条匹配纵向路径组成的受控组合。
_Avoid_: T 型单条 Skill、完整 Skill graph

**Oracle Loading（Oracle 加载）**:
根据人工冻结的任务标签直接加载正确 Skill，不经过 Router。
_Avoid_: 检索、预测

**Mechanism Pilot（机制 Pilot）**:
复用已见测试 case、只检查实现和效应方向的小规模实验，不提供独立 held-out 结论。
_Avoid_: 正式确认、独立复现

**State-aware Checkpoint（状态感知检查点）**:
跨任务的确定性横向控制：对时间推进操作定期要求显式观测，对其他命令只在命令、分数和 observation 都未变化时判定停滞。
_Avoid_: 按任务名分支的专用解法
