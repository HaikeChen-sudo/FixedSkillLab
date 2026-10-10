# 报告目录

报告以 Markdown 发布，正文、表格和图片可直接在 GitHub 阅读。图片保存在对应报告目录中；下载单篇 `.md` 时，需要同时保留其引用的图片目录。

## 当前项目结论

- [项目说明与结果复核](../docs/PROJECT_SUMMARY.md)
- [中文技术报告](../docs/research/fixedskilllab_paper_draft_2026-10-09.md)
- [主张—证据表](../docs/research/fixedskilllab_claim_evidence_2026-10-09.md)

## 历史阶段报告

这些报告保留各阶段的实验记录与当时判断。后续审计可能限制早期结论的解释范围，请结合上方的当前项目说明阅读；旧报告中的“下一步”不是当前执行计划。

| 报告 | 范围 |
| --- | --- |
| [Mini Lab 阶段科研报告](legacy/Mini_Lab_阶段科研报告.md) | 最小环境与初步对照 |
| [ALFWorld v7](legacy/ALFWorld_固定Skill研究报告_v7.md) | 固定 Skill 开发与定向测试 |
| [ALFWorld v8](legacy/ALFWorld_固定Skill研究报告_v8.md) | 后续确认实验 |
| [ScienceWorld v9](legacy/ScienceWorld_固定Skill检索正式实验报告_v9.md) | 固定 Skill 检索实验 |
| [ScienceWorld v10](legacy/ScienceWorld_固定Skill检索发现与确认报告_v10.md) | 发现与确认结果对照 |
| [ScienceWorld v11b](scienceworld_v11b/ScienceWorld_固定Skill检索平衡确认报告_v11b.md) | 平衡确认实验 |
| [ScienceWorld v13b](scienceworld_v13b/ScienceWorld_固定Skill_Procedure定向确认报告_v13b.md) | Procedure 定向确认 |

## PDF 转换说明

2026-10-10 将仓库中的 5 份正式 PDF 转为 `legacy/` 下的 Markdown。转换使用对应 Word 原稿恢复段落和表格，再与已发布 PDF 核对；保留 35 张表和 13 幅原图，去除页眉、页脚和分页。图片保持原来的颜色与分辨率，实验数字和历史结论未重写。

GitHub Markdown 表格不沿用 PDF 的三线表版式。原表内容仍可复制、检索；单元格内的换行保留为 `<br>`。原稿中分行的终端命令补上续行符，便于复制执行；这些命令属于历史复现说明，不建议直接启动付费实验。

[转换核对清单](legacy/conversion_manifest.json)记录源文件版本、SHA-256、正文及表格核对数量、输出与图片哈希。原 PDF 保存在本地忽略目录 `.local-report-backups/pdf-2026-10-10/`，不再随当前版本发布；既有 Git 历史不改写。
