"""Create publication-style figures for the v7 targeted ALFWorld study."""

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ORDER = ("no_skill", "oracle_v5", "oracle_v7")
LABELS = {"no_skill": "No Skill", "oracle_v5": "Oracle v5", "oracle_v7": "Oracle v7"}
COLORS = {"no_skill": "#64748B", "oracle_v5": "#D97706", "oracle_v7": "#2563EB"}


def read_csv(path):
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def style():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial Unicode MS", "PingFang SC", "Arial", "DejaVu Sans"],
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#94A3B8", "axes.labelcolor": "#334155",
        "xtick.color": "#475569", "ytick.color": "#475569",
        "text.color": "#0F172A", "figure.facecolor": "white", "axes.facecolor": "white",
    })


def save(fig, path):
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def profile(summary, output):
    lookup = {row["condition"]: row for row in summary}
    specs = (
        ("task_success_rate", "成功率 (%)", 100),
        ("average_total_tokens", "平均 Total Tokens", 1),
        ("average_latency_ms", "平均端到端延迟 (s)", 0.001),
        ("cost_per_successful_task_usd", "单次成功成本 (USD)", 1),
    )
    fig, axes = plt.subplots(2, 2, figsize=(10.2, 6.5))
    for ax, (field, title, scale) in zip(axes.flat, specs):
        values = [float(lookup[name][field]) * scale for name in ORDER]
        bars = ax.bar(range(3), values, color=[COLORS[name] for name in ORDER], width=0.62)
        ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
        ax.set_xticks(range(3), [LABELS[name] for name in ORDER], fontsize=9)
        ax.grid(axis="y", color="#E2E8F0", linewidth=0.7)
        ax.set_axisbelow(True)
        if field == "task_success_rate":
            ax.set_ylim(70, 103)
        for bar, value in zip(bars, values):
            if field == "task_success_rate":
                label = f"{value:.1f}%"
            elif field == "average_total_tokens":
                label = f"{value/1000:.1f}k"
            elif field == "average_latency_ms":
                label = f"{value:.1f}s"
            else:
                label = f"${value:.6f}"
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(), label, ha="center", va="bottom", fontsize=8)
    fig.suptitle("v7 独立定向测试：质量与推理开销", fontsize=14, fontweight="bold", x=0.06, ha="left")
    fig.text(0.06, 0.01, "10 个 valid_unseen 任务 × 3 次重复；每个条件 n=30 episodes", fontsize=9, color="#64748B")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94), h_pad=2.0)
    save(fig, output / "v7_method_profile.png")


def frontier(summary, output):
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    for row in summary:
        name = row["condition"]
        x = float(row["cost_per_successful_task_usd"])
        y = 100 * float(row["task_success_rate"])
        ax.scatter(x, y, s=125, color=COLORS[name], edgecolor="#0F172A", linewidth=0.7, zorder=3)
        ax.annotate(LABELS[name], (x, y), xytext=(7, 7 if name != "oracle_v5" else -15), textcoords="offset points", fontsize=10)
    ax.set_xlabel("单次成功成本 (USD)  →")
    ax.set_ylabel("任务成功率 (%)  ↑")
    ax.set_title("质量—成本位置", loc="left", fontsize=13, fontweight="bold")
    ax.text(0.01, 0.98, "理想方向：左上", transform=ax.transAxes, va="top", fontsize=9, color="#64748B")
    ax.grid(color="#E2E8F0", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.set_ylim(86, 102)
    fig.tight_layout()
    save(fig, output / "v7_quality_cost_frontier.png")


def outcomes(tasks, output):
    task_ids = sorted({row["task_id"] for row in tasks})
    lookup = {(row["task_id"], row["condition"]): float(row["task_success_rate"]) for row in tasks}
    matrix = np.array([[lookup[(task, condition)] for task in task_ids] for condition in ORDER])
    fig, ax = plt.subplots(figsize=(9.2, 3.0))
    image = ax.imshow(matrix, vmin=0, vmax=1, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(task_ids)), [item.split(":")[-1] for item in task_ids], fontsize=9)
    ax.set_yticks(range(3), [LABELS[name] for name in ORDER], fontsize=10)
    ax.set_xlabel("任务编号（valid_unseen）")
    ax.set_title("逐任务成功率", loc="left", fontsize=13, fontweight="bold")
    for i in range(3):
        for j in range(len(task_ids)):
            value = matrix[i, j]
            ax.text(j, i, f"{int(round(value*3))}/3", ha="center", va="center", fontsize=9,
                    color="white" if value > 0.65 else "#0F172A")
    colorbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    colorbar.set_label("成功率")
    fig.tight_layout()
    save(fig, output / "v7_task_success_heatmap.png")


def family(families, output):
    names = ("heat_then_place", "two_object_place")
    family_labels = ("加热后放置", "双物体放置")
    lookup = {(row["condition"], row["task_family"]): row for row in families}
    x = np.arange(2)
    width = 0.24
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.8))
    for index, condition in enumerate(ORDER):
        success = [100 * float(lookup[(condition, family)]["task_success_rate"]) for family in names]
        tokens = [float(lookup[(condition, family)]["average_total_tokens"]) / 1000 for family in names]
        axes[0].bar(x + (index-1)*width, success, width, label=LABELS[condition], color=COLORS[condition])
        axes[1].bar(x + (index-1)*width, tokens, width, label=LABELS[condition], color=COLORS[condition])
    axes[0].set_title("成功率 (%)", loc="left", fontweight="bold")
    axes[0].set_ylim(70, 103)
    axes[1].set_title("平均 Total Tokens (千)", loc="left", fontweight="bold")
    for ax in axes:
        ax.set_xticks(x, family_labels)
        ax.grid(axis="y", color="#E2E8F0", linewidth=0.7)
        ax.set_axisbelow(True)
    axes[0].legend(frameon=False, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.02))
    fig.suptitle("任务类别分解", fontsize=13, fontweight="bold", x=0.06, ha="left", y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    save(fig, output / "v7_family_profile.png")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("analysis_dir", type=Path)
    args = parser.parse_args()
    output = args.analysis_dir / "figures"
    output.mkdir(parents=True, exist_ok=True)
    style()
    summary = read_csv(args.analysis_dir / "condition_summary.csv")
    tasks = read_csv(args.analysis_dir / "task_summary.csv")
    families = read_csv(args.analysis_dir / "family_summary.csv")
    profile(summary, output)
    frontier(summary, output)
    outcomes(tasks, output)
    family(families, output)
    print(json.dumps({"figures": sorted(str(path) for path in output.glob("*.png"))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
