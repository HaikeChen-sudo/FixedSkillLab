# ScienceWorld：12 个新开发实例的 Semantic 检索检查

日期：2026-09-25。实验性质：开发集离线筛查；没有运行 Agent，也没有调用 DeepSeek。

## 结论

在预先冻结的 12 个官方 dev 实例上，Semantic Flat 的 Gold Hit@1 为 10/12，Semantic Body 为 12/12。两组的 Gold Hit@3 都是 12/12。

两处分歧都来自 `find-non-living-thing` 家族。Flat 将 `find-living-object` 排在第一位，将正确的 `find-nonliving-object` 排在第二位；Body 将正确 Skill 排在第一位。其余 10 个实例的第一名相同。

这个结果支持做一次小规模、针对性的 Top-1 执行检查。它尚不能证明正文检索提高任务成功率，也不能证明差异来自复杂 Procedure 理解。否定词、Skill 命名和描述表述都可能影响这一排序。

## 选题与冻结

先按规则选题，再读取任务文本，最后计算排名。使用原始 `GOLD_SKILLS` 的全部六个家族，每个家族选择两个在历史记录中未出现过的官方 dev 编号，按编号升序选择，不按检索结果或 Agent 成败选题。

历史排查覆盖项目根目录 Python 文件、注册任务套件、`docs` 下 Markdown、`results` 下 JSON/JSONL，共 219 个文件，识别出六个家族的 74 个历史实例及 165 个查询文本哈希。排查不覆盖项目外文件、`tmp` 和二进制报告。因此，“新实例”指本次可检查记录中未出现，不是对全部历史操作的绝对保证。

| 任务家族 | 本轮官方 dev 编号 | Gold Skill |
| --- | --- | --- |
| boil | 014、015 | boil-substance |
| find-living-thing | 150、151 | find-living-object |
| find-non-living-thing | 150、151 | find-nonliving-object |
| freeze | 014、015 | freeze-substance |
| melt | 014、015 | melt-substance |
| use-thermometer | 270、271 | measure-and-classify-temperature |

本轮统一使用历史 v3 库中的六个 Skill。上轮缓存检查涉及 v4/v4b/v4c/v4d 的四个新增家族；不能将两轮合并成一个跨库总体，也不能将本轮差异解释成版本升级收益。

清单在新题文本读取前保存，包含选题规则、实例、Skill 库、编码器文件、依赖版本、官方划分快照和代码哈希。本地 ScienceWorld 1.2.3 再次核对六个家族的 dev 列表与快照一致，然后仅执行加载与 reset，提取 `info['taskDesc']`。未执行任务动作，未读取 Gold 路径，未使用官方 test 实例。

## 检索设置

编码器沿用已冻结的本地 `all-MiniLM-L6-v2`，CPU、384 维、归一化向量、最大长度 256 token。超长输入会报错，不截断、不换题。Flat 索引 Name 与 Description；Body 索引完整 Skill。两组候选库、查询和编码器相同。

Gold 标签仅用于排名后的判定，未加入查询或编码器输入。排序使用未取整的余弦分数，分数相同时按 Skill 名称排序。本轮保存完整排名，并计算假设加载 Top-1/Top-3 完整 Skill 时的提示文本哈希；这些是待加载文本，不是已执行的 Agent 输入。

## 结果及重复文本

| 指标 | 12 个任务实例 | 9 个不同查询＋Gold |
| --- | ---: | ---: |
| Flat Gold Hit@1 | 10/12（83.33%） | 7/9（77.78%） |
| Body Gold Hit@1 | 12/12（100%） | 9/9（100%） |
| Flat Gold Hit@3 | 12/12（100%） | 9/9（100%） |
| Body Gold Hit@3 | 12/12（100%） | 9/9（100%） |
| Top-1 不同 | 2/12 | 2/9 |
| Top-3 集合不同 | 4/12 | 2/9 |
| Top-3 有序列表不同 | 8/12 | 5/9 |
| Top-1 完整提示相同 | 10/12 | 7/9 |
| Top-3 完整提示相同 | 4/12 | 4/9 |

boil、freeze、melt 各自的两个实例使用相同任务描述，合计重复三条查询。本轮保留冻结清单中的全部实例，不为增加不同文本的数量而补题。九种查询均未命中已收集的历史查询哈希；这只说明精确文本不同，不代表语义或任务模板新颖。

两条非生物查询分别要求放入厨房的红盒子和绿盒子，同属一个任务模板。不能把它们当成两个独立任务家族，更不能依据 12/12 宣称检索器具有普遍优势。

| 分歧实例 | Flat 第一名 | Body 第一名 | Flat Gold 排名 | Body Gold 排名 |
| --- | --- | --- | ---: | ---: |
| find-non-living-thing:v150 | find-living-object | find-nonliving-object | 2 | 1 |
| find-non-living-thing:v151 | find-living-object | find-nonliving-object | 2 | 1 |

## 验证与未测量指标

脚本复用现有检索与 Skill 渲染函数，没有修改在线 Agent、原始 Skill 或旧实验文件。额外使用现有在线适配器的 `minilm_scores`，逐查询复算两种索引的完整排名，检查批量编码是否改变排序；核验结果保存在 `verification.json`。

本轮没有新增以下六项 Agent 指标：Task Success Rate、Input Tokens、Output Tokens、Total Tokens、End-to-End Latency、Cost per Successful Task。编码器输入长度只用于检查截断，不是 DeepSeek 的输入 Token 账单。Gold Hit@1 也不是任务成功率。

## 下一步建议：只检查分歧是否影响执行

可准备 4 个开发实例的小规模机制 Pilot：两条非生物分歧实例，加上编号相同的两条生物实例作为无分歧对照。比较 No Skill、Semantic Flat Top-1、Semantic Body Top-1，每组重复三次，共 36 个 episode。两种检索均加载完整 Skill，执行模型、预算和工具协议保持一致。

这四个实例的选择受本次离线结果影响，应标为针对性开发诊断，不能称为独立确认或总体收益估计。重点是：错误第一名是否影响执行，以及 Body 是否比 No Skill 更好；仅胜过被错误 Skill 干扰的 Flat 不足以证明 Skill 有净收益。

本轮未实现 Top-1 在线条件，也未启动这 36 个 episode。在线入口及费用边界应在执行前另行冻结。若只观察到单一家族的命名／否定词问题，应缩小研究结论，不将它扩写成通用正文检索优势。

## 文件与复查

- `scienceworld_top1_dev_probe.py`：选题、收集、排名，三个阶段分开执行，均无 API 调用入口。
- `test_scienceworld_top1_dev_probe.py`：选题、划分、历史记录识别与排名差异计数测试。
- `results/scienceworld_top1_new_dev_12/manifest.json`：查询读取前冻结的清单与哈希。
- 同目录 `queries.json`：官方开发任务描述。
- 同目录 `audit.json`：完整排名、实例汇总、去重汇总及提示文本哈希。
- 同目录 `verification.json`：现有适配器逐查询复算的核验记录。

三个写入阶段已完成，不要再次运行 `prepare`、`collect` 或 `rank` 覆盖结果。查看清单及文件状态：

```sh
python3 scienceworld_top1_dev_probe.py status
python3 -m unittest test_scienceworld_top1_dev_probe test_scienceworld_top1_audit -v
```

`status` 校验冻结代码与配置，并报告文件是否存在；它不重新执行环境任务或重算排名。
