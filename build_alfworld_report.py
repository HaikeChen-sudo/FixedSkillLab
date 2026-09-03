"""Build the Chinese ALFWorld stage report from the frozen JSONL run."""

import argparse
import json
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from result_utils import deduplicate_records
from plot_alfworld_results import LABELS, ORDER, plot_rows
from summarize_results import summarize_by_repeat


FONT = "SimSun"
INK = RGBColor(11, 37, 69)
BLUE = RGBColor(46, 116, 181)
LIGHT = "F2F4F7"


def set_font(run, size=11, bold=None, color=None):
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:ascii"), FONT)
    run._element.rPr.rFonts.set(qn("w:hAnsi"), FONT)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color is not None:
        run.font.color.rgb = color


def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_border(parent, edge, value, size="8", color="000000"):
    borders = parent.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = parent.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders" if parent.tag.endswith("tblPr") else "w:tcBorders")
        parent.append(borders)
    border = borders.find(qn(f"w:{edge}"))
    if border is None:
        border = OxmlElement(f"w:{edge}")
        borders.append(border)
    border.set(qn("w:val"), value)
    border.set(qn("w:sz"), size)
    border.set(qn("w:color"), color)


def set_cell_text(cell, text, bold=False, size=8.5, header=False):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run(text)
    set_font(run, size=size, bold=bold, color=INK if header else None)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    if header:
        set_border(cell._tc.get_or_add_tcPr(), "bottom", "single", "8")


def set_table_geometry(table, widths):
    table.autofit = False
    # The default template has no portable "Table Normal" style name.
    # Borders are set explicitly below so the result stays a three-line table.
    tbl_width = table._tbl.tblPr.first_child_found_in("w:tblW")
    if tbl_width is None:
        tbl_width = OxmlElement("w:tblW")
        table._tbl.tblPr.append(tbl_width)
    tbl_width.set(qn("w:w"), str(sum(widths)))
    tbl_width.set(qn("w:type"), "dxa")
    table_indent = table._tbl.tblPr.first_child_found_in("w:tblInd")
    if table_indent is None:
        table_indent = OxmlElement("w:tblInd")
        table._tbl.tblPr.append(table_indent)
    table_indent.set(qn("w:w"), "120")
    table_indent.set(qn("w:type"), "dxa")
    set_border(table._tbl.tblPr, "top", "single", "12")
    set_border(table._tbl.tblPr, "bottom", "single", "12")
    for edge in ("left", "right", "insideH", "insideV"):
        set_border(table._tbl.tblPr, edge, "nil", "0")
    grid = table._tbl.tblGrid.gridCol_lst
    for grid_col, width in zip(grid, widths):
        grid_col.set(qn("w:w"), str(width))
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            cell.width = Inches(width / 1440)
            cell_width = cell._tc.tcPr.first_child_found_in("w:tcW")
            if cell_width is None:
                cell_width = OxmlElement("w:tcW")
                cell._tc.tcPr.append(cell_width)
            cell_width.set(qn("w:w"), str(width))
            cell_width.set(qn("w:type"), "dxa")


def add_paragraph(doc, text="", bold_prefix=None):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.10
    if bold_prefix and text.startswith(bold_prefix):
        run = paragraph.add_run(bold_prefix)
        set_font(run, bold=True)
        run = paragraph.add_run(text[len(bold_prefix):])
        set_font(run)
    else:
        run = paragraph.add_run(text)
        set_font(run)
    return paragraph


def add_heading(doc, text, level=1):
    paragraph = doc.add_paragraph(style=f"Heading {level}")
    paragraph.paragraph_format.space_before = Pt(16 if level == 1 else 12)
    paragraph.paragraph_format.space_after = Pt(8 if level == 1 else 6)
    run = paragraph.add_run(text)
    set_font(run, size=16 if level == 1 else 13, bold=True, color=BLUE if level == 1 else INK)
    return paragraph


def add_caption(doc, text):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(3)
    paragraph.paragraph_format.space_after = Pt(8)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(text)
    set_font(run, size=9, color=RGBColor(89, 89, 89))


def failure_evidence(records):
    lookup = {(row["task_id"], row["repeat"], row["condition"]): row["success"] for row in records}
    failed = [row for row in records if not row["success"]]
    retrieval = [row for row in failed if row["condition"] in {"flat_retrieval", "body_aware_retrieval"} and lookup[(row["task_id"], row["repeat"], "oracle_skill")]]
    all_interference = [row for row in failed if row["condition"] == "all_skills" and lookup[(row["task_id"], row["repeat"], "no_skill")]]
    oracle_interference = [row for row in failed if row["condition"] == "oracle_skill" and lookup[(row["task_id"], row["repeat"], "no_skill")]]
    shared_execution = [row for row in failed if row["condition"] == "oracle_skill" and not lookup[(row["task_id"], row["repeat"], "no_skill")]]
    return {
        "failed": len(failed),
        "two_object": sum(row.get("task_family") == "two_object_place" for row in failed),
        "retrieval": len(retrieval),
        "all_interference": len(all_interference),
        "oracle_interference": len(oracle_interference),
        "shared_execution": len(shared_execution),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the ALFWorld stage report")
    parser.add_argument("results", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--figures-dir", type=Path, default=Path("results/figures"))
    parser.add_argument("--output", type=Path, default=Path("ALFWorld_固定Skill阶段实验报告.docx"))
    args = parser.parse_args()
    records = [json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = [row for row in records if row.get("run_id") == args.run_id]
    records, _ = deduplicate_records(records)
    if len(records) != 450:
        parser.error("this report expects the completed 450-episode frozen run")
    rows = plot_rows(records)
    evidence = failure_evidence(records)

    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Inches(1)
    section.left_margin = section.right_margin = Inches(1)
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    normal.font.size = Pt(11)
    for style_name in ("Heading 1", "Heading 2"):
        doc.styles[style_name].font.name = FONT
        doc.styles[style_name]._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_font(header.add_run("ALFWorld 固定 Skill 实验 | 阶段报告"), size=8.5, color=RGBColor(89, 89, 89))
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(footer.add_run("实验运行：alfworld-v3-30x3 | 2026-08-31"), size=8.5, color=RGBColor(89, 89, 89))

    title = doc.add_paragraph()
    title.paragraph_format.space_after = Pt(4)
    set_font(title.add_run("Fixed-Skill Routing in ALFWorld: Stage Report"), size=21, bold=True, color=INK)
    subtitle = doc.add_paragraph()
    subtitle.paragraph_format.space_after = Pt(14)
    set_font(subtitle.add_run("DeepSeek · valid_unseen · 30 fixed tasks · 5 conditions · 3 repeats"), size=11, color=RGBColor(89, 89, 89))

    add_heading(doc, "摘要", 1)
    add_paragraph(doc, "本实验在文字版 ALFWorld 的固定 30 题任务集上比较五种 Skill 加载方式：No Skill、All Skills、Flat Retrieval、Body-aware Retrieval 与 Oracle Skill。五个条件共享同一 DeepSeek 模型、工具循环和 50 步上限，每个条件重复 3 次，共 450 个 episode。All Skills 的成功率最高（96.7%），但平均总 token 是 No Skill 的 2.5 倍。Oracle Skill 的成功率为 95.6%，成本与 No Skill 接近；Flat Retrieval 的成功率最低（92.2%）。失败轨迹表明，当前固定 Skill 库的主要问题不是单纯缺少 Skill，而是路由遗漏和长轨迹执行失败并存。")
    add_paragraph(doc, "关键词：LLM Agent；ALFWorld；Skill Retrieval；Inference Cost；Failure Analysis")

    add_heading(doc, "1. 方法")
    add_paragraph(doc, "任务集固定为 ALFWorld valid_unseen 中的 30 道题，覆盖加热后放置、冷却后放置、清洁后放置、双物体放置、灯光检查和简单放置六类目标。每类 5 题。")
    add_paragraph(doc, "五组实验使用同一 DeepSeek 模型、温度 0、同一 Agent 控制循环、同一 50 步上限和同一环境。环境返回 won=true 才计为成功，模型不能自行评分。总计 450 个 episode。")
    table = doc.add_table(rows=1, cols=2)
    set_table_geometry(table, [2100, 7260])
    set_cell_text(table.rows[0].cells[0], "条件", True, 9, True)
    set_cell_text(table.rows[0].cells[1], "加载内容", True, 9, True)
    condition_text = [
        ("No Skill", "不加载 Skill，直接由模型调用 act(command)。"),
        ("All Skills", "加载全部 30 个固定 Skill。"),
        ("Flat Retrieval", "按 Skill 的 Name 与 Description 检索 Top-3。"),
        ("Body-aware Retrieval", "检索时同时使用 Name、Description 与 Procedure。"),
        ("Oracle Skill", "加载人工标注的 Gold Skill。"),
    ]
    for name, description in condition_text:
        cells = table.add_row().cells
        set_cell_text(cells[0], name)
        set_cell_text(cells[1], description)

    add_heading(doc, "2. 评价指标")
    add_paragraph(doc, "Task Success Rate = 成功 episode 数 / 总 episode 数。每个 episode 还记录 Input Tokens、Output Tokens、Total Tokens、端到端延迟、单次成功成本与工具调用数。单次成功成本定义为该条件全部 episode 的模型调用成本之和除以成功 episode 数；模型价格来自运行器配置。")

    add_heading(doc, "3. 结果")
    add_paragraph(doc, "表中为三次重复的均值 ± 样本标准差。每个条件共 90 个 episode，每次重复包含相同 30 道任务。")
    result_table = doc.add_table(rows=1, cols=8)
    set_table_geometry(result_table, [1300, 800, 1100, 850, 1150, 850, 1700, 1610])
    headers = ["方法", "成功率", "输入\nTokens", "输出\nTokens", "总\nTokens", "延迟\n(s)", "成本/成功\n(USD)", "工具\n调用"]
    for cell, text in zip(result_table.rows[0].cells, headers):
        set_cell_text(cell, text, True, 8, True)
    repeat_summaries = {item["condition"]: item for item in summarize_by_repeat(records)}
    for row in rows:
        cells = result_table.add_row().cells
        values = [
            row["label"],
            f'{row["task_success_rate"]["mean"] * 100:.1f} ± {row["task_success_rate"]["std"] * 100:.1f}%',
            f'{row.get("average_input_tokens", {}).get("mean", 0):,.0f}',
            "—",
            f'{row["average_total_tokens"]["mean"]:,.0f}',
            "—",
            f'${row["cost_per_successful_task_usd"]["mean"]:.6f}',
            "—",
        ]
        summary = repeat_summaries[row["condition"]]
        values[2] = f'{summary["average_input_tokens"]["mean"]:,.0f}'
        values[3] = f'{summary["average_output_tokens"]["mean"]:,.0f}'
        values[5] = f'{summary["average_latency_ms"]["mean"] / 1000:.2f}'
        values[7] = f'{summary["average_tool_calls"]["mean"]:.2f}'
        for cell, value in zip(cells, values):
            set_cell_text(cell, value, size=7.5)

    add_caption(doc, "表 1  ALFWorld valid_unseen 上的结果。成功率为均值 ± 样本标准差；其余数值为三次重复的均值。每个条件为 90 个 episode。")
    add_paragraph(doc, "All Skills 的成功率最高，为 96.7%，但平均总 token 为 89,984，是 No Skill 的约 2.5 倍。Flat Retrieval 的成功率最低，且比 No Skill 更慢、更贵。")
    add_paragraph(doc, "Oracle Skill 的均值成功率为 95.6%，略高于 No Skill 的 94.4%；两者的成本和延迟接近。三次重复不足以做显著性判断，这里只把它视为后续改进路由器的信号。")

    figures = [
        ("alfworld_method_profile.png", "图 1  五个条件的成功率、总 token、端到端延迟和单次成功成本（均值 ± 样本标准差）。"),
        ("alfworld_quality_cost_frontier.png", "图 2  成功率与单次成功成本的关系。左上方向表示更低成本和更高成功率。"),
        ("alfworld_failure_heatmap.png", "图 3  六个出现失败的任务在五种条件下的失败 episode 数。每个条件重复 3 次。"),
    ]
    for filename, caption in figures:
        path = args.figures_dir / filename
        if not path.exists():
            parser.error(f"missing figure: {path}")
        doc.add_picture(str(path), width=Inches(6.2))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_caption(doc, caption)

    add_heading(doc, "4. 失败分析")
    add_paragraph(doc, f'450 个 episode 中有 {evidence["failed"]} 个失败；其中 {evidence["two_object"]} 个（75%）属于双物体放置任务。失败集中在 valid_unseen:049 与 valid_unseen:090。')
    analysis_table = doc.add_table(rows=1, cols=3)
    set_table_geometry(analysis_table, [2820, 900, 5640])
    for cell, text in zip(analysis_table.rows[0].cells, ["对照证据", "次数", "解释"]):
        set_cell_text(cell, text, True, 9, True)
    analysis_rows = [
        ("Selective Retrieval 失败、同题同次 Oracle 成功", str(evidence["retrieval"]), "可确认的检索遗漏。"),
        ("All Skills 失败、同题同次 No Skill 成功", str(evidence["all_interference"]), "可能存在 Skill 干扰。"),
        ("Oracle 失败、同题同次 No Skill 也失败", str(evidence["shared_execution"]), "说明正确 Skill 仍不能解决执行难点。"),
        ("Oracle 失败、同题同次 No Skill 成功", str(evidence["oracle_interference"]), "可能是 Gold Skill 干扰或未被遵循。"),
    ]
    for evidence_name, count, interpretation in analysis_rows:
        cells = analysis_table.add_row().cells
        for cell, text in zip(cells, (evidence_name, count, interpretation)):
            set_cell_text(cell, text, size=8.5)
    add_paragraph(doc, "任务 040 是最清楚的路由错误：Flat Retrieval 连续两次漏掉 execute-cool-place，而其他四种条件都成功。任务 090 则在 No Skill、Flat、Body-aware 和 Oracle 中均有失败，问题是长轨迹里的对象状态跟踪、编号和动作恢复，不能简单归为路由错误。")

    doc.add_page_break()
    add_heading(doc, "5. 讨论")
    add_paragraph(doc, "在当前 30 个固定 Skill、哈希检索器和 30 题 ALFWorld 套件下，Skill 加载没有稳定带来性价比提升。All Skills 能提高成功率，但成本明显上升；Flat Retrieval 低于 No Skill；Body-aware Retrieval 没有超过 No Skill。Oracle 与 No Skill 的差异很小，说明当前 Skill 内容本身没有提供足够强的优势，或模型已经能从环境反馈中完成大部分轨迹。")
    add_paragraph(doc, "下一轮应冻结 Agent、任务集、Skill 库和评价方式，只替换检索器：将当前哈希检索基线换成语义 embedding 检索，并保留 Flat Top-3、Body-aware Top-3 和 Oracle 对照。检索器应同时报告 Gold Skill 的 Recall@3 与 MRR，才能把路由质量和最终成功率分开分析。")
    add_heading(doc, "6. 局限性")
    for text in [
        "任务集只有 30 道固定 valid_unseen 任务，不能代表 ALFWorld 全部任务。",
        "每组只有 3 次重复；均值差异不能直接解释为统计显著差异。",
        "当前检索器是确定性的本地哈希基线，不是预训练语义 embedding。",
        "成本来自运行时的模型定价配置，价格变化时需要重新计算。",
    ]:
        paragraph = doc.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(4)
        set_font(paragraph.add_run(text), size=10.5)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
