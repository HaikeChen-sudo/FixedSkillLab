# Procedure holdout 的官方 split 核对记录

2026-09-22 02:02 UTC。本记录更新[执行前登记](scienceworld_procedure_holdout_prereg_2026-09-22.md)中的 split 状态，不改题号、P0/P1 文本、指标或判定规则。

我在本机启动已安装的 ScienceWorld，分别加载 `chemistry-mix` 与 `inclined-plane-determine-angle` 的 train variation 0，然后调用 `get_variations_test()`。返回的 test 列表各有 8 和 42 个编号；化学 v027–v029、斜面 v129–v131 均在相应列表内。核对没有调用 DeepSeek，没有读取这六道题的任务描述或动作轨迹。先前因本地 Java 网关停滞而写下的“split 尚未核对”已过期。

运行器在付费调用前仍会重复这项检查。代码及离线审计共 55 项本地测试通过，预览列出 36 个 episode。当前尚未执行 holdout episode；下一步是先提交协议快照，再决定是否运行模型。
