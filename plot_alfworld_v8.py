"""Create publication figures for the v8 ALFWorld confirmation study."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from plot_alfworld_v7 import COLORS, LABELS, ORDER, read_csv, save, style


def metric_profile(summary, output):
    lookup = {row["condition"]: row for row in summary}
    specs = (
        ("task_success_rate", "Task Success Rate", 100, lambda x: f"{x:.1f}%"),
        ("average_input_tokens", "Input Tokens", 0.001, lambda x: f"{x:.1f}k"),
        ("average_output_tokens", "Output Tokens", 1, lambda x: f"{x:,.0f}"),
        ("average_total_tokens", "Total Tokens", 0.001, lambda x: f"{x:.1f}k"),
        ("average_latency_ms", "End-to-End Latency", 0.001, lambda x: f"{x:.1f}s"),
        ("cost_per_successful_task_usd", "Cost per Successful Task", 1, lambda x: f"${x:.6f}"),
    )
    fig, axes = plt.subplots(2, 3, figsize=(11.2, 6.4))
    for ax, (field, title, scale, formatter) in zip(axes.flat, specs):
        values = [float(lookup[name][field]) * scale for name in ORDER]
        bars = ax.bar(range(3), values, color=[COLORS[name] for name in ORDER], width=0.62,
                      edgecolor="#334155", linewidth=0.5)
        ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold")
        ax.set_xticks(range(3), [LABELS[name] for name in ORDER], fontsize=8.5)
        ax.grid(axis="y", color="#E2E8F0", linewidth=0.7)
        ax.set_axisbelow(True)
        if field == "task_success_rate":
            ax.set_ylim(94, 100.8)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(), formatter(value),
                    ha="center", va="bottom", fontsize=7.7)
    fig.suptitle("v8 确认实验的六项核心指标", x=0.06, ha="left", fontsize=14, fontweight="bold")
    fig.text(0.06, 0.012, "20 个 task-disjoint valid_seen 任务 × 3 次重复；每个条件 n=60 episodes",
             fontsize=8.8, color="#64748B")
    fig.tight_layout(rect=(0, 0.045, 1, 0.94), w_pad=1.7, h_pad=2.1)
    save(fig, output / "v8_six_metric_profile.png")


def frontier(summary, output):
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    for row in summary:
        name = row["condition"]
        x, y = float(row["cost_per_successful_task_usd"]), 100 * float(row["task_success_rate"])
        ax.scatter(x, y, s=135, color=COLORS[name], edgecolor="#0F172A", linewidth=0.7, zorder=3)
        offset = {"no_skill": (7, -13), "oracle_v5": (7, -2), "oracle_v7": (7, 8)}[name]
        ax.annotate(LABELS[name], (x, y), xytext=offset, textcoords="offset points", fontsize=9.5)
    ax.annotate("理想方向", xy=(0.00073, 100.05), xytext=(0.00086, 99.25),
                arrowprops={"arrowstyle": "->", "color": "#475569"}, fontsize=9, color="#475569")
    ax.set_xlabel("Cost per Successful Task (USD)  →")
    ax.set_ylabel("Task Success Rate (%)  ↑")
    ax.set_title("v8 质量与成本位置", loc="left", fontsize=13, fontweight="bold")
    ax.grid(color="#E2E8F0", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.set_ylim(97.8, 100.35)
    fig.tight_layout()
    save(fig, output / "v8_quality_cost_frontier.png")


def task_deltas(rows, output):
    rows = sorted(rows, key=lambda row: float(row["total_tokens_difference"]))
    labels = [row["task_id"].split(":")[-1] for row in rows]
    values = [float(row["total_tokens_difference"]) / 1000 for row in rows]
    colors = ["#2563EB" if row["task_family"] == "heat_then_place" else "#D97706" for row in rows]
    fig, ax = plt.subplots(figsize=(8.8, 6.2))
    y = np.arange(len(rows))
    ax.barh(y, values, color=colors, edgecolor="#334155", linewidth=0.45)
    ax.axvline(0, color="#0F172A", linewidth=1)
    ax.set_yticks(y, labels)
    ax.set_xlabel("Oracle v7 - No Skill 的平均 Total Tokens（千）")
    ax.set_ylabel("任务编号（valid_seen）")
    fig.suptitle("逐任务 Total Tokens 差值", x=0.08, y=0.985, ha="left", fontsize=13, fontweight="bold")
    fig.text(0.08, 0.945, "蓝：加热后放置；橙：双物体放置；负值表示 v7 更省",
             fontsize=8.8, color="#64748B")
    ax.grid(axis="x", color="#E2E8F0", linewidth=0.7)
    ax.set_axisbelow(True)
    for yi, value in zip(y, values):
        ax.text(value + (3 if value >= 0 else -3), yi, f"{value:+.1f}k",
                va="center", ha="left" if value >= 0 else "right", fontsize=7.2)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    save(fig, output / "v8_task_token_differences.png")


def family_profile(families, output):
    names = ("heat_then_place", "two_object_place")
    family_labels = ("加热后放置\n6 tasks / 18 episodes", "双物体放置\n14 tasks / 42 episodes")
    lookup = {(row["condition"], row["task_family"]): row for row in families}
    x, width = np.arange(2), 0.24
    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.9))
    specs = (
        ("task_success_rate", "成功率 (%)", 100),
        ("average_total_tokens", "平均 Total Tokens (千)", 0.001),
        ("average_latency_ms", "平均延迟 (s)", 0.001),
    )
    for ax, (field, title, scale) in zip(axes, specs):
        for index, condition in enumerate(ORDER):
            values = [float(lookup[(condition, family)][field]) * scale for family in names]
            ax.bar(x + (index - 1) * width, values, width, label=LABELS[condition], color=COLORS[condition],
                   edgecolor="#334155", linewidth=0.4)
        ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold")
        ax.set_xticks(x, family_labels, fontsize=8.2)
        ax.grid(axis="y", color="#E2E8F0", linewidth=0.7)
        ax.set_axisbelow(True)
        if field == "task_success_rate": ax.set_ylim(94, 101)
    axes[0].legend(frameon=False, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.06), fontsize=8.5)
    fig.suptitle("任务族分解", x=0.06, y=0.99, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.90), w_pad=1.7)
    save(fig, output / "v8_family_profile.png")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("analysis_dir", type=Path)
    args = parser.parse_args()
    output = args.analysis_dir / "figures"
    output.mkdir(parents=True, exist_ok=True)
    style()
    metric_profile(read_csv(args.analysis_dir / "condition_summary.csv"), output)
    frontier(read_csv(args.analysis_dir / "condition_summary.csv"), output)
    task_deltas(read_csv(args.analysis_dir / "task_differences.csv"), output)
    family_profile(read_csv(args.analysis_dir / "family_summary.csv"), output)
    print(json.dumps({"figures": sorted(str(path) for path in output.glob("*.png"))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
