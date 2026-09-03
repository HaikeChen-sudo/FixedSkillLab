"""Build the Chinese technical report for the frozen ALFWorld v4 run."""

import argparse
import json
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


FONT = "Arial Unicode MS"
INK = RGBColor(11, 37, 69)
BLUE = RGBColor(46, 116, 181)
GRAY = RGBColor(89, 89, 89)
CONDITION_ORDER = (
    "no_skill", "body_aware_retrieval", "bm25_body_retrieval", "oracle_skill", "all_skills",
)
LABELS = {
    "no_skill": "No Skill",
    "body_aware_retrieval": "Body-aware",
    "bm25_body_retrieval": "BM25 Body",
    "oracle_skill": "Oracle Skill",
    "all_skills": "All Skills",
}


def set_font(run, size=11, bold=None, color=None):
    run.font.name = FONT
    for key in ("w:ascii", "w:hAnsi", "w:eastAsia"):
        run._element.get_or_add_rPr().get_or_add_rFonts().set(qn(key), FONT)
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color is not None:
        run.font.color.rgb = color


def set_border(parent, edge, value, size="8", color="000000"):
    tag = "w:tblBorders" if parent.tag.endswith("tblPr") else "w:tcBorders"
    borders = parent.first_child_found_in(tag)
    if borders is None:
        borders = OxmlElement(tag)
        parent.append(borders)
    border = borders.find(qn(f"w:{edge}"))
    if border is None:
        border = OxmlElement(f"w:{edge}")
        borders.append(border)
    border.set(qn("w:val"), value)
    border.set(qn("w:sz"), size)
    border.set(qn("w:color"), color)


def set_table_geometry(table, widths):
    table.autofit = False
    width = table._tbl.tblPr.first_child_found_in("w:tblW") or OxmlElement("w:tblW")
    if width.getparent() is None:
        table._tbl.tblPr.append(width)
    width.set(qn("w:w"), str(sum(widths)))
    width.set(qn("w:type"), "dxa")
    indent = table._tbl.tblPr.first_child_found_in("w:tblInd") or OxmlElement("w:tblInd")
    if indent.getparent() is None:
        table._tbl.tblPr.append(indent)
    indent.set(qn("w:w"), "120")
    indent.set(qn("w:type"), "dxa")
    set_border(table._tbl.tblPr, "top", "single", "12")
    set_border(table._tbl.tblPr, "bottom", "single", "12")
    for edge in ("left", "right", "insideH", "insideV"):
        set_border(table._tbl.tblPr, edge, "nil", "0")
    for grid_col, cell_width in zip(table._tbl.tblGrid.gridCol_lst, widths):
        grid_col.set(qn("w:w"), str(cell_width))
    for row in table.rows:
        for cell, cell_width in zip(row.cells, widths):
            cell.width = Inches(cell_width / 1440)
            tc_width = cell._tc.tcPr.first_child_found_in("w:tcW") or OxmlElement("w:tcW")
            if tc_width.getparent() is None:
                cell._tc.tcPr.append(tc_width)
            tc_width.set(qn("w:w"), str(cell_width))
            tc_width.set(qn("w:type"), "dxa")


def set_cell(cell, text, header=False, size=8, align=WD_ALIGN_PARAGRAPH.CENTER):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.alignment = align
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.0
    run = paragraph.add_run(str(text))
    set_font(run, size=size, bold=header, color=INK if header else None)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    if header:
        set_border(cell._tc.get_or_add_tcPr(), "bottom", "single", "8")


def paragraph(doc, text="", bold_prefix=None):
    item = doc.add_paragraph()
    item.paragraph_format.space_after = Pt(6)
    item.paragraph_format.line_spacing = 1.10
    if bold_prefix and text.startswith(bold_prefix):
        set_font(item.add_run(bold_prefix), bold=True)
        set_font(item.add_run(text[len(bold_prefix):]))
    else:
        set_font(item.add_run(text))
    return item


def heading(doc, text, level=1):
    item = doc.add_paragraph(style=f"Heading {level}")
    item.paragraph_format.space_before = Pt(16 if level == 1 else 12)
    item.paragraph_format.space_after = Pt(8 if level == 1 else 6)
    set_font(item.add_run(text), size=16 if level == 1 else 13, bold=True, color=BLUE if level == 1 else INK)
    return item


def caption(doc, text):
    item = doc.add_paragraph()
    item.alignment = WD_ALIGN_PARAGRAPH.CENTER
    item.paragraph_format.space_before = Pt(3)
    item.paragraph_format.space_after = Pt(8)
    set_font(item.add_run(text), size=9, color=GRAY)


def bullet(doc, text):
    item = doc.add_paragraph(style="List Bullet")
    item.paragraph_format.space_after = Pt(4)
    item.paragraph_format.line_spacing = 1.10
    set_font(item.add_run(text), size=10.5)


def add_page_field(paragraph):
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend((begin, instruction, end))
    set_font(run, size=8.5, color=GRAY)


def main():
    parser = argparse.ArgumentParser(description="Build the ALFWorld v4 formal report")
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--figures-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.analysis.read_text(encoding="utf-8"))
    summaries = {row["condition"]: row for row in data["condition_summary"]}
    paired = {row["condition"]: row for row in data["paired_comparisons"]}
    taxonomy = {row["category"]: row for row in data["failure_taxonomy"]}
    retrieval = data["retrieval_audit"]

    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Inches(1)
    section.left_margin = section.right_margin = Inches(1)
    section.header_distance = section.footer_distance = Inches(0.492)
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.10
    for style_name in ("Heading 1", "Heading 2"):
        doc.styles[style_name].font.name = FONT
        doc.styles[style_name]._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)

    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_font(header.add_run("ALFWorld 固定 Skill 路由实验 | 正式分析"), size=8.5, color=GRAY)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(footer.add_run("alfworld-v4-heldout-30x3  |  "), size=8.5, color=GRAY)
    add_page_field(footer)

    title = doc.add_paragraph()
    title.paragraph_format.space_after = Pt(4)
    set_font(title.add_run("ALFWorld 中固定 Skill 路由的效果与推理成本"), size=21, bold=True, color=INK)
    subtitle = doc.add_paragraph()
    subtitle.paragraph_format.space_after = Pt(14)
    set_font(subtitle.add_run("DeepSeek-v4-flash · 独立测试集30题 · 5个条件 · 3次重复 · 450 episodes"), size=10.5, color=GRAY)

    heading(doc, "技术摘要")
    paragraph(doc, "在这组独立测试上，固定 Skill 没有提高任务成功率。No Skill 达到 98.89%，并且拥有最低的输入 token、总 token、端到端延迟和单次成功成本，是唯一处于质量—成本 Pareto 前沿的方法。All Skills、Body-aware、BM25 Body 与 Oracle Skill 相对 No Skill 的配对成功率差异均为负，按任务成组重采样得到的95%置信区间都包含0。现有证据不支持“加载固定 Skill 能改善 ALFWorld Agent”的结论。")
    paragraph(doc, "BM25 的离线主 Skill Hit@3 曾达到93.3%，实际 Agent 运行只有76.7%。代码核查发现两种评测使用的查询不同：离线基准使用任务目标句，在线 Agent 使用包含场景物品和容器的完整初始观察。该差异会污染检索词，是下一轮应单独检验的机制问题。")
    paragraph(doc, "关键词：LLM Agent；ALFWorld；Skill Retrieval；推理成本；负结果；失败分析")

    heading(doc, "1. No Skill 同时取得最高成功率和最低成本")
    paragraph(doc, "表1列出预先确定的六项核心指标。成功率的不确定性同时报告三次重复的样本标准差和按任务成组重采样的95%置信区间。后者把同一道题的三次运行一起抽样，避免把90个 episode 全部当成相互独立样本。")
    table = doc.add_table(rows=1, cols=8)
    widths = [1250, 950, 1200, 1000, 850, 1000, 900, 2210]
    set_table_geometry(table, widths)
    headers = ("方法", "成功率\n均值±SD", "95% CI", "Input\nTokens", "Output\nTokens", "Total\nTokens", "延迟\n(s)", "成本/成功\n(USD)")
    for cell, text in zip(table.rows[0].cells, headers):
        set_cell(cell, text, header=True, size=7.3)
    for condition in CONDITION_ORDER:
        row = summaries[condition]
        values = (
            LABELS[condition],
            f'{100 * row["task_success_rate"]:.2f}±{100 * row["success_rate_repeat_std"]:.2f}%',
            f'{100 * row["success_ci_low"]:.2f}–{100 * row["success_ci_high"]:.2f}%',
            f'{row["average_input_tokens"]:,.0f}',
            f'{row["average_output_tokens"]:,.0f}',
            f'{row["average_total_tokens"]:,.0f}',
            f'{row["average_latency_ms"] / 1000:.2f}',
            f'${row["cost_per_successful_task_usd"]:.6f}',
        )
        for index, (cell, value) in enumerate(zip(table.add_row().cells, values)):
            set_cell(cell, value, size=7.1, align=WD_ALIGN_PARAGRAPH.LEFT if index == 0 else WD_ALIGN_PARAGRAPH.CENTER)
    caption(doc, "表1  独立测试集上的总体结果。每种条件90个 episode；CI按30个任务成组重采样20,000次。")
    paragraph(doc, "No Skill 相比 Body-aware 少24.5%的总 token，相比 BM25 Body 少48.4%，相比 All Skills 少66.7%。BM25 Body 每个成功任务的成本约为 No Skill 的1.61倍，成功率却低3.33个百分点。")

    profile = args.figures_dir / "alfworld_method_profile.png"
    doc.add_picture(str(profile), width=Inches(6.2))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(doc, "图1  五种条件的成功率、总 token、端到端延迟和单次成功成本。误差线为三次重复的样本标准差。")
    paragraph(doc, "图1中的成功率都很高，但成本差异很大。All Skills 的输入上下文最长；BM25 Body 的工具调用次数也更多，因此它没有把更好的离线检索转化成更短的轨迹。")

    frontier = args.figures_dir / "alfworld_quality_cost_frontier.png"
    doc.add_picture(str(frontier), width=Inches(6.1))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(doc, "图2  质量—成本关系。左上方向表示更高成功率和更低单次成功成本。")
    paragraph(doc, "No Skill 位于其余四种方法的左上方。当前数据中不存在以更高成本换取更高成功率的折中，因而不能把 Skill 方法描述为质量—成本前沿改进。")

    heading(doc, "2. 配对比较未发现 Skill 带来的成功率增益")
    paragraph(doc, "每个条件使用相同任务和重复编号，因此比较采用任务级配对重采样。差值定义为 Skill 条件成功率减去 No Skill 成功率；负值表示 Skill 条件更差。")
    paired_table = doc.add_table(rows=1, cols=4)
    set_table_geometry(paired_table, [2600, 1800, 2600, 2360])
    for cell, text in zip(paired_table.rows[0].cells, ("对比条件", "差值（百分点）", "95% CI（百分点）", "Bootstrap p")):
        set_cell(cell, text, header=True, size=8)
    for condition in ("body_aware_retrieval", "bm25_body_retrieval", "oracle_skill", "all_skills"):
        row = paired[condition]
        values = (LABELS[condition], f'{100 * row["difference"]:.2f}', f'{100 * row["ci_low"]:.2f}–{100 * row["ci_high"]:.2f}', f'{row["bootstrap_p_value"]:.3f}')
        for index, (cell, value) in enumerate(zip(paired_table.add_row().cells, values)):
            set_cell(cell, value, size=8, align=WD_ALIGN_PARAGRAPH.LEFT if index == 0 else WD_ALIGN_PARAGRAPH.CENTER)
    caption(doc, "表2  相对 No Skill 的任务级配对重采样结果。p值用于描述证据强度，不作多重比较校正。")
    paragraph(doc, "所有区间都覆盖0，不能排除这些差异来自有限任务集和运行随机性。BM25 Body 的点估计最差，但样本仍不足以把它解释为稳定的性能下降。这里能确定的是：没有观察到正向收益。")

    heading(doc, "3. 双物体放置决定了大部分失败")
    paragraph(doc, "六类任务中，Clean、Cool、Light 和 Simple Place 在所有条件下均达到100%。差异主要来自 Two objects；No Skill 为93.3%，Body-aware、BM25 Body 和 Oracle Skill 均为80.0%。")
    family = args.figures_dir / "alfworld_family_success_heatmap.png"
    doc.add_picture(str(family), width=Inches(6.25))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(doc, "图3  各条件在六类任务上的成功率。每个单元包含5题×3次重复，共15个 episode。")
    paragraph(doc, "这种集中性说明总体成功率已经接近天花板。当前任务集真正区分方法的是多物体状态跟踪，而不是大多数单物体任务。后续测试集应保留类别平衡，并单独报告 Two objects。")

    failure = args.figures_dir / "alfworld_failure_heatmap.png"
    doc.add_picture(str(failure), width=Inches(6.1))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(doc, "图4  三次重复中出现失败的任务及条件。数字为失败 episode 数。")
    paragraph(doc, "14次失败只分布在任务010、026和050。按同题同次对照，9次属于 Skill 条件失败而 No Skill 成功，4次属于 No Skill 与 Oracle 同时失败，只有1次满足“检索漏掉主 Skill 且 Oracle 成功”的严格路由错误定义。该分类是轨迹对照结果，不等同于人工因果标注。")

    taxonomy_table = doc.add_table(rows=1, cols=3)
    set_table_geometry(taxonomy_table, [3300, 1200, 4860])
    for cell, text in zip(taxonomy_table.rows[0].cells, ("失败类别", "次数", "占全部失败")):
        set_cell(cell, text, header=True, size=8.5)
    taxonomy_labels = {
        "routing_error": "严格路由错误",
        "shared_execution_error": "共享执行错误",
        "skill_condition_interference": "Skill 条件干扰或执行偏移",
    }
    for category in ("routing_error", "shared_execution_error", "skill_condition_interference"):
        row = taxonomy.get(category, {"failures": 0, "share": 0})
        values = (taxonomy_labels[category], row["failures"], f'{100 * row["share"]:.1f}%')
        for index, (cell, value) in enumerate(zip(taxonomy_table.add_row().cells, values)):
            set_cell(cell, value, size=8.5, align=WD_ALIGN_PARAGRAPH.LEFT if index == 0 else WD_ALIGN_PARAGRAPH.CENTER)
    caption(doc, "表3  基于配对轨迹的互斥失败分类。")

    heading(doc, "4. 离线检索优势没有进入 Agent 轨迹")
    paragraph(doc, f'BM25 Body 在实际运行中命中主 Gold Skill 的任务为{retrieval["primary_gold_hit_at_3_tasks"]}/30，Hit@3为{100 * retrieval["primary_gold_hit_at_3_task_rate"]:.1f}%。命中时成功率为{100 * retrieval["success_when_hit"]:.1f}%，未命中时为{100 * retrieval["success_when_missed"]:.1f}%。二者有明显相关，但不能据此断言检索命中导致成功，因为任务难度同时影响命中和执行。')
    paragraph(doc, "离线基准使用 game.tw-pddl grammar 中的任务目标；在线 Agent 把完整初始观察传给检索器。场景中的大量物品名、容器名和状态词会改变BM25词频。下一版 Router 应只提取“Your task is to:”后的目标句，先在开发集验证检索一致性，再使用新的独立测试集评估端到端效果。")

    heading(doc, "5. 实验范围与指标定义")
    paragraph(doc, "实验使用 ALFWorld valid_unseen 中预先冻结的30道任务，六类任务各5道。五种条件使用同一 DeepSeek-v4-flash 模型、温度0、同一工具协议和50步上限，每题重复3次。成功仅由环境 won=true 判定，模型不参与评分。")
    for text in (
        "Task Success Rate：成功 episode 数除以该条件总 episode 数。",
        "Input Tokens：全部模型调用的输入 token；Output Tokens：模型生成 token；Total Tokens 为二者之和。",
        "End-to-End Latency：从环境重置、路由、模型调用、工具交互到结束的总时间。",
        "Cost per Successful Task：该条件全部 episode 的推理成本之和除以成功 episode 数。",
    ):
        bullet(doc, text)
    paragraph(doc, "成本按运行器中 DeepSeek-v4-flash 的缓存命中、缓存未命中和输出 token 单价计算。价格变化会改变绝对成本，但不会改变本次记录中的 token 数。")

    heading(doc, "6. 限制与稳健性")
    for text in (
        "测试集只有30道题。95%以上的总体成功率使方法差异只能由少数难题决定。",
        "三次重复仍不足以估计很小的成功率差异；配对区间包含0，结果应写成负结果而非方法排名定论。",
        "失败分类依赖同题同次对照和轨迹字段，只能识别与路由、Skill 条件或共同执行相关的模式，不能证明因果。",
        "当前 held-out 集已经用于正式分析，后续任何 Router 或 Skill 修改都不能继续用它调参。",
    ):
        bullet(doc, text)

    heading(doc, "7. 下一步：把查询构造与 Skill 内容分开验证")
    paragraph(doc, "下一轮只改一个变量：Router 查询从完整初始观察改为任务目标句。修改先在原开发集上验证，检查在线与离线BM25 Top-3是否一致；Skill库、模型、工具协议和步数上限保持不变。随后从剩余未使用的 valid_unseen 任务中冻结新的30题测试集。")
    paragraph(doc, "如果修正后 BM25 的检索命中提高，但端到端成功率仍不超过 No Skill，就说明瓶颈主要在 Skill 内容或模型执行，而不是 Router。如果成功率提高但 token 和延迟仍明显上升，则研究问题转为是否存在可接受的质量—成本折中。")

    heading(doc, "数据与复现信息")
    paragraph(doc, f'冻结运行：{data["manifest"]["run_id"]}；记录数：{data["manifest"]["records"]}；SHA-256：{data["manifest"]["sha256"]}。原始轨迹、统计表、失败摘要和绘图数据均保存在项目 results/formal_v4 目录。')

    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
