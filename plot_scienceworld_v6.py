"""Create figures for the formal ScienceWorld router experiment."""

import argparse
import json
from collections import Counter
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from plot_alfworld_v7 import read_csv, save, style


ORDER = ("no_skill", "all_skills", "flat_retrieval", "body_aware_retrieval", "oracle_v3")
LABELS = {
    "no_skill": "No Skill",
    "all_skills": "All Skills",
    "flat_retrieval": "Flat",
    "body_aware_retrieval": "Body-aware",
    "oracle_v3": "Oracle v3",
}
COLORS = {
    "no_skill": "#64748B",
    "all_skills": "#D97706",
    "flat_retrieval": "#EAB308",
    "body_aware_retrieval": "#2563EB",
    "oracle_v3": "#1E3A8A",
}


def metric_profile(rows, output):
    lookup = {row["condition"]: row for row in rows}
    specs = (
        ("task_success_rate", "Task Success Rate", 100, lambda value: f"{value:.1f}%"),
        ("average_input_tokens", "Input Tokens", 0.001, lambda value: f"{value:.0f}k"),
        ("average_output_tokens", "Output Tokens", 1, lambda value: f"{value:,.0f}"),
        ("average_total_tokens", "Total Tokens", 0.001, lambda value: f"{value:.0f}k"),
        ("average_latency_ms", "End-to-End Latency", 0.001, lambda value: f"{value:.1f}s"),
        ("cost_per_successful_task_usd", "Cost per Successful Task", 1, lambda value: f"${value:.4f}"),
    )
    fig, axes = plt.subplots(2, 3, figsize=(12.2, 6.8))
    for ax, (field, title, scale, formatter) in zip(axes.flat, specs):
        values = [float(lookup[name][field]) * scale for name in ORDER]
        bars = ax.bar(range(len(ORDER)), values, color=[COLORS[name] for name in ORDER], width=0.68,
                      edgecolor="#334155", linewidth=0.45)
        ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold")
        ax.set_xticks(range(len(ORDER)), [LABELS[name] for name in ORDER], fontsize=7.8, rotation=18, ha="right")
        ax.grid(axis="y", color="#E2E8F0", linewidth=0.7)
        ax.set_axisbelow(True)
        ax.margins(y=0.18)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), formatter(value),
                    ha="center", va="bottom", fontsize=7.3)
    fig.suptitle("ScienceWorld v6 正式实验的六项核心指标", x=0.055, ha="left",
                 fontsize=14, fontweight="bold")
    fig.text(0.055, 0.012, "12 个 test variation × 5 个条件 × 3 次重复；每个条件 n=36 episodes",
             fontsize=8.8, color="#64748B")
    fig.tight_layout(rect=(0, 0.055, 1, 0.94), w_pad=1.5, h_pad=1.8)
    save(fig, output / "scienceworld_v6_six_metrics.png")


def frontier(rows, output):
    fig, ax = plt.subplots(figsize=(8.0, 4.9))
    lookup = {row["condition"]: row for row in rows}
    for name in ORDER:
        row = lookup[name]
        x = float(row["cost_per_successful_task_usd"])
        y = 100 * float(row["task_success_rate"])
        marker = "D" if name == "body_aware_retrieval" else ("^" if name == "oracle_v3" else "o")
        ax.scatter(x, y, s=145, marker=marker, color=COLORS[name], edgecolor="#0F172A", linewidth=0.7, zorder=3)
        offsets = {
            "no_skill": (7, -13), "all_skills": (7, 7), "flat_retrieval": (7, 7),
            "body_aware_retrieval": (7, -14), "oracle_v3": (7, 7),
        }
        ax.annotate(LABELS[name], (x, y), xytext=offsets[name], textcoords="offset points", fontsize=9.2)
    ax.annotate("理想方向", xy=(0.0026, 96.3), xytext=(0.0039, 84),
                arrowprops={"arrowstyle": "->", "color": "#475569"}, fontsize=9, color="#475569")
    ax.text(0.02, 0.96, "菱形：可检索方法    三角形：Oracle 上界", transform=ax.transAxes,
            va="top", fontsize=8.5, color="#64748B")
    ax.set_xlabel("Cost per Successful Task (USD)  →")
    ax.set_ylabel("Task Success Rate (%)  ↑")
    ax.set_title("质量与成功成本", loc="left", fontsize=13, fontweight="bold")
    ax.grid(color="#E2E8F0", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.set_xlim(0.0023, 0.0076)
    ax.set_ylim(66, 98)
    fig.tight_layout()
    save(fig, output / "scienceworld_v6_quality_cost.png")


def task_heatmap(rows, output):
    task_ids = []
    for row in rows:
        if row["task_id"] not in task_ids:
            task_ids.append(row["task_id"])
    lookup = {(row["task_id"], row["condition"]): int(row["successes"]) for row in rows}
    matrix = np.array([[lookup[(task, condition)] for task in task_ids] for condition in ORDER])
    short_names = {
        "boil": "boil", "melt": "melt", "freeze": "freeze",
        "use-thermometer": "thermometer", "find-living-thing": "living",
        "find-non-living-thing": "nonliving",
    }
    labels = [f'{short_names[task.split(":v")[0]]}\nv{task.split(":v")[1]}' for task in task_ids]
    fig, ax = plt.subplots(figsize=(11.4, 4.0))
    image = ax.imshow(matrix, vmin=0, vmax=3, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(task_ids)), labels, fontsize=7.6)
    ax.set_yticks(range(len(ORDER)), [LABELS[name] for name in ORDER], fontsize=9)
    for row_index in range(len(ORDER)):
        for column_index in range(len(task_ids)):
            value = matrix[row_index, column_index]
            ax.text(column_index, row_index, f"{value}/3", ha="center", va="center",
                    fontsize=8.0, color="white" if value >= 2 else "#0F172A")
    colorbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02, ticks=(0, 1, 2, 3))
    colorbar.set_label("三次重复中的成功次数", fontsize=8.5)
    ax.set_title("逐任务成功次数", loc="left", fontsize=13, fontweight="bold")
    ax.set_xlabel("官方 test variation")
    fig.tight_layout()
    save(fig, output / "scienceworld_v6_task_heatmap.png")


def retrieval_and_failures(retrieval_rows, failure_path, output):
    names = [row["condition"] for row in retrieval_rows]
    x = np.arange(len(names))
    width = 0.24
    hit = [100 * float(row["gold_hit_at_3_rate"]) for row in retrieval_rows]
    success_hit = [100 * float(row["success_rate_when_hit"]) for row in retrieval_rows]
    success_miss = [100 * float(row["success_rate_when_missed"]) for row in retrieval_rows]

    failures = [json.loads(line) for line in failure_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    categories = (
        "environment_move_budget_exhausted", "premature_model_stop", "execution_error_other",
    )
    category_labels = ("动作预算耗尽", "模型提前停止", "其他执行错误")
    category_colors = ("#475569", "#D97706", "#93C5FD")
    counts = Counter((row["condition"], row["category"]) for row in failures)

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.7), gridspec_kw={"width_ratios": (1.03, 1.25)})
    ax = axes[0]
    for offset, values, label, color in (
        (-width, hit, "Gold Hit@3", "#1E3A8A"),
        (0, success_hit, "命中时成功率", "#2563EB"),
        (width, success_miss, "漏检时成功率", "#D97706"),
    ):
        bars = ax.bar(x + offset, values, width, label=label, color=color, edgecolor="#334155", linewidth=0.4)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 1.2, f"{value:.1f}%",
                    ha="center", va="bottom", fontsize=7.5)
    ax.set_xticks(x, [LABELS[name] for name in names])
    ax.set_ylim(0, 108)
    ax.set_title("检索命中与执行成功", loc="left", fontsize=11, fontweight="bold")
    ax.legend(frameon=False, fontsize=7.8, loc="lower center", ncol=3)
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.7)
    ax.set_axisbelow(True)

    ax = axes[1]
    y = np.arange(len(ORDER))
    left = np.zeros(len(ORDER))
    for category, label, color in zip(categories, category_labels, category_colors):
        values = np.array([counts[(name, category)] for name in ORDER])
        ax.barh(y, values, left=left, label=label, color=color, edgecolor="white", linewidth=0.6)
        for index, value in enumerate(values):
            if value:
                ax.text(left[index] + value / 2, index, str(value), ha="center", va="center",
                        fontsize=8, color="white" if color != "#93C5FD" else "#0F172A")
        left += values
    ax.set_yticks(y, [LABELS[name] for name in ORDER])
    ax.invert_yaxis()
    ax.set_xlabel("失败 episode 数")
    ax.set_title("失败构成", loc="left", fontsize=11, fontweight="bold")
    ax.legend(frameon=False, fontsize=7.8, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3)
    ax.grid(axis="x", color="#E2E8F0", linewidth=0.7)
    ax.set_axisbelow(True)
    fig.suptitle("Router 诊断与失败分析", x=0.055, ha="left", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0.08, 1, 0.92), w_pad=2.2)
    save(fig, output / "scienceworld_v6_retrieval_failures.png")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("analysis_dir", type=Path)
    args = parser.parse_args()
    output = args.analysis_dir / "figures"
    output.mkdir(parents=True, exist_ok=True)
    style()
    condition_rows = read_csv(args.analysis_dir / "condition_summary.csv")
    metric_profile(condition_rows, output)
    frontier(condition_rows, output)
    task_heatmap(read_csv(args.analysis_dir / "task_summary.csv"), output)
    retrieval_and_failures(read_csv(args.analysis_dir / "retrieval_summary.csv"),
                           args.analysis_dir / "failures.jsonl", output)
    print(json.dumps({"figures": sorted(str(path) for path in output.glob("*.png"))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
