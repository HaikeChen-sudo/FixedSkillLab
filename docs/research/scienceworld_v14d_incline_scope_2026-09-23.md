# ScienceWorld v14d：斜面 Skill 适用范围修正

日期：2026-09-23。状态：Skill 与下一道 dev 题号已冻结；尚未读取新题题面，未调用 DeepSeek。离线审计在本机启动 Java 网关时卡住，已中止；没有产出新题记录，需在用户终端重试。

## v14c 复盘

`scienceworld-v14c-dev-check-4x1` 共 4 道 dev 题 × 2 条件，8/8 成功。Body-aware v4c 平均输入 97,697 tokens、输出 1,409 tokens、总计 99,106 tokens、延迟 26.07 秒、每成功题估算费用 $0.001586；Oracle v4c 分别为 92,850、1,416、94,266 tokens、24.86 秒、$0.001563。没有同题 No Skill 基线，不能据此判断 Skill 是否带来增益。

其中斜面 `v085` 的题面要求选 **steepest**，但 v4c 的 Description、Activation、Procedure 和 Termination 都只定义了 **shallowest**。两条条件虽然都得到 100 分，成功不能消除这一语义错误；离线 Gold Hit@3 也只检查 Skill 名称，不能证明被检索的 Procedure 适用。此题从此只作开发诊断，不作新版本的确认题。

## 修正范围与检查顺序

v4d 仅覆盖 `measure-inclined-plane-angle`：先读题目要求最浅还是最陡；同一滑块在两条斜面上分别计到滑块到底；时间较长对应较浅，较短对应较陡；最后聚焦题目要求的那条斜面。v4c 与更早版本原样保留，运行记录使用独立的 `_v4d` 条件名和库哈希。

下一道题预先定为 `inclined-plane-determine-angle:v086`，属于开发检查，不是 test。先用无 API 的审计核对官方 dev split、完整题面、Flat/Body 的 Gold 排名，以及题目问的是最浅还是最陡。若 split 不对、题目不在这两种方向内，或检索未命中，停下并记录；不得换一道“好过”的题冒充原定检查。

若审计通过，再决定是否在这一道题上各跑一次 Body-aware v4d 与 Oracle v4d。一次运行仍是调试，不报告显著性，也不启动原 v14 的正式 test。已有分支查看过同任务类型的部分 test variation；即使换新编号，也不能称整个斜面任务类型为完全盲测。
