"""Create the colored figures used by the ScienceWorld v11b Markdown report."""

import csv
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from plot_alfworld_v7 import save, style
from analyze_scienceworld_formal import paired_statistics
from scienceworld_suites import (
    SCIENCEWORLD_V6_ROUTER_FORMAL_12,
    SCIENCEWORLD_V10_CONFIRM_12,
    SCIENCEWORLD_V11B_CONFIRM_18,
)


ROOT = Path(__file__).resolve().parent
ANALYSIS_DIR = ROOT / "results" / "formal_scienceworld_v11"
FIGURE_DIR = ANALYSIS_DIR / "figures"
ORDER = ("no_skill", "flat_retrieval", "body_aware_retrieval")
LABELS = {
    "no_skill": "No Skill",
    "flat_retrieval": "Flat Retrieval",
    "body_aware_retrieval": "Body-aware Retrieval",
}
COLORS = {
    "no_skill": "#64748B",
    "flat_retrieval": "#D97706",
    "body_aware_retrieval": "#2563EB",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path):
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def repeat_lookup(summary):
    return {row["condition"]: row for row in summary["repeat_statistics"]}


def core_metrics(summary):
    repeats = repeat_lookup(summary)
    specs = (
        ("task_success_rate", "任务成功率", 100, lambda value: f"{value:.1f}%"),
        ("average_input_tokens", "Input Tokens", 0.001, lambda value: f"{value:.0f}k"),
        ("average_output_tokens", "Output Tokens", 1, lambda value: f"{value:,.0f}"),
        ("average_total_tokens", "Total Tokens", 0.001, lambda value: f"{value:.0f}k"),
        ("average_latency_ms", "端到端延迟", 0.001, lambda value: f"{value:.1f}s"),
        ("cost_per_successful_task_usd", "单次成功成本", 1, lambda value: f"${value:.4f}"),
    )
    fig, axes = plt.subplots(2, 3, figsize=(12.4, 6.9))
    for ax, (field, title, scale, formatter) in zip(axes.flat, specs):
        values = [repeats[name][field]["mean"] * scale for name in ORDER]
        errors = [repeats[name][field]["std"] * scale for name in ORDER]
        bars = ax.bar(
            range(len(ORDER)), values, yerr=errors, capsize=4,
            color=[COLORS[name] for name in ORDER], width=0.64,
            edgecolor="#334155", linewidth=0.5,
        )
        ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
        ax.set_xticks(range(len(ORDER)), [LABELS[name] for name in ORDER], fontsize=8.2)
        ax.grid(axis="y", color="#E2E8F0", linewidth=0.7)
        ax.set_axisbelow(True)
        ax.set_ylim(bottom=0)
        ax.margins(y=0.28)
        for bar, value, error in zip(bars, values, errors):
            ax.text(
                bar.get_x() + bar.get_width() / 2, value + error,
                formatter(value), ha="center", va="bottom", fontsize=7.8,
            )
    fig.suptitle(
        "ScienceWorld v11b：六项核心指标",
        x=0.055, ha="left", fontsize=14.5, fontweight="bold",
    )
    fig.text(
        0.055, 0.012,
        "18 道 test variation × 3 条件 × 3 次重复；柱高为重复均值，误差线为重复间样本标准差。",
        fontsize=8.8, color="#64748B",
    )
    fig.tight_layout(rect=(0, 0.055, 1, 0.94), w_pad=1.4, h_pad=1.9)
    save(fig, FIGURE_DIR / "scienceworld_v11b_core_metrics.png")


def quality_cost_frontier(summary):
    repeats = repeat_lookup(summary)
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    markers = {"no_skill": "o", "flat_retrieval": "s", "body_aware_retrieval": "D"}
    offsets = {
        "no_skill": (-76, 10),
        "flat_retrieval": (10, -18),
        "body_aware_retrieval": (10, 9),
    }
    for name in ORDER:
        row = repeats[name]
        x = row["cost_per_successful_task_usd"]["mean"]
        y = 100 * row["task_success_rate"]["mean"]
        xerr = row["cost_per_successful_task_usd"]["std"]
        yerr = 100 * row["task_success_rate"]["std"]
        ax.errorbar(
            x, y, xerr=xerr, yerr=yerr, fmt=markers[name], markersize=10,
            color=COLORS[name], ecolor=COLORS[name], elinewidth=1.2, capsize=4,
            markeredgecolor="#0F172A", markeredgewidth=0.7, zorder=3,
        )
        ax.annotate(
            LABELS[name], (x, y), xytext=offsets[name], textcoords="offset points",
            fontsize=9.5,
        )
    ax.annotate(
        "理想方向",
        xy=(0.0022, 93.5), xytext=(0.0046, 79.0),
        arrowprops={"arrowstyle": "->", "color": "#475569"},
        color="#475569", fontsize=9,
    )
    ax.set_xlabel("单次成功成本 (USD)  →")
    ax.set_ylabel("任务成功率 (%)  ↑")
    ax.set_title("质量—成本位置", loc="left", fontsize=13.5, fontweight="bold")
    ax.grid(color="#E2E8F0", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.set_xlim(left=0)
    ax.set_ylim(68, 98)
    fig.text(0.13, 0.01, "误差线为 3 次重复的样本标准差。", fontsize=8.6, color="#64748B")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, FIGURE_DIR / "scienceworld_v11b_quality_cost.png")


def task_heatmap(rows):
    task_ids = []
    for row in rows:
        if row["task_id"] not in task_ids:
            task_ids.append(row["task_id"])
    lookup = {(row["task_id"], row["condition"]): int(row["successes"]) for row in rows}
    matrix = np.array([[lookup[(task, condition)] for task in task_ids] for condition in ORDER])
    short = {
        "boil": "boil", "melt": "melt", "freeze": "freeze",
        "use-thermometer": "therm.", "find-living-thing": "living",
        "find-non-living-thing": "nonliving",
    }
    labels = [f'{short[item.split(":v")[0]]}\nv{item.split(":v")[1]}' for item in task_ids]
    fig, ax = plt.subplots(figsize=(12.2, 3.5))
    image = ax.imshow(matrix, vmin=0, vmax=3, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(task_ids)), labels, fontsize=7.8)
    ax.set_yticks(range(len(ORDER)), [LABELS[name] for name in ORDER], fontsize=9)
    for row_index in range(len(ORDER)):
        for column_index in range(len(task_ids)):
            value = matrix[row_index, column_index]
            ax.text(
                column_index, row_index, f"{value}/3", ha="center", va="center",
                fontsize=8.2, color="white" if value >= 2 else "#0F172A",
            )
    for position in (2.5, 5.5, 8.5, 11.5, 14.5):
        ax.axvline(position, color="white", linewidth=2.0)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02, ticks=(0, 1, 2, 3))
    colorbar.set_label("三次重复中的成功次数", fontsize=8.5)
    ax.set_title("逐任务成功次数", loc="left", fontsize=13.5, fontweight="bold")
    ax.set_xlabel("官方 test variation（每三列为一个任务类型）")
    fig.tight_layout()
    save(fig, FIGURE_DIR / "scienceworld_v11b_task_success.png")


def replication_figure():
    studies = (
        (
            "v9 发现",
            ROOT / "results" / "formal_scienceworld_v6",
            "scienceworld-v6-router-formal-12x3.jsonl",
            SCIENCEWORLD_V6_ROUTER_FORMAL_12,
        ),
        (
            "v10 确认",
            ROOT / "results" / "formal_scienceworld_v10",
            "scienceworld-v10-confirm-12x3.jsonl",
            SCIENCEWORLD_V10_CONFIRM_12,
        ),
        (
            "v11b 平衡确认",
            ANALYSIS_DIR,
            "scienceworld-v11b-confirm-18x3.jsonl",
            SCIENCEWORLD_V11B_CONFIRM_18,
        ),
    )
    labels, success, success_low, success_high = [], [], [], []
    token_difference, token_low, token_high = [], [], []
    for label, directory, records_name, tasks in studies:
        records = [
            json.loads(line)
            for line in (directory / records_name).read_text(encoding="utf-8").splitlines()
            if line.strip() and json.loads(line)["condition"] in ("no_skill", "body_aware_retrieval")
        ]
        paired = paired_statistics(
            records, tasks, ("no_skill", "body_aware_retrieval"), 3,
            seed=20260915,
        )[0]
        labels.append(label)
        success.append(100 * paired["success_rate_difference"])
        success_low.append(100 * paired["task_cluster_bootstrap_ci_low"])
        success_high.append(100 * paired["task_cluster_bootstrap_ci_high"])
        token_difference.append(paired["average_total_tokens_difference"] / 1000)
        token_low.append(paired["total_tokens_cluster_bootstrap_ci_low"] / 1000)
        token_high.append(paired["total_tokens_cluster_bootstrap_ci_high"] / 1000)

    x = np.arange(len(labels))
    colors = ("#93C5FD", "#60A5FA", "#2563EB")
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.3))
    values_and_bounds = (
        (success, success_low, success_high, "Body-aware 的成功率差", "相对 No Skill（百分点）"),
        (
            token_difference, token_low, token_high,
            "Body-aware 的平均 Total Tokens 差",
            "Body-aware − No Skill（千 Token）",
        ),
    )
    for ax, (values, lows, highs, title, ylabel) in zip(axes, values_and_bounds):
        yerr = np.array([
            [value - low for value, low in zip(values, lows)],
            [high - value for value, high in zip(values, highs)],
        ])
        bars = ax.bar(x, values, yerr=yerr, capsize=5, width=0.62, color=colors,
                      edgecolor="#334155", linewidth=0.5)
        ax.axhline(0, color="#475569", linewidth=0.9)
        ax.set_xticks(x, labels, fontsize=9)
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc="left", fontsize=11.5, fontweight="bold")
        ax.grid(axis="y", color="#E2E8F0", linewidth=0.7)
        ax.set_axisbelow(True)
        for bar, value, low, high in zip(bars, values, lows, highs):
            label_y = high if value >= 0 else low
            ax.text(
                bar.get_x() + bar.get_width() / 2, label_y, f"{value:.1f}",
                ha="center", va="bottom" if value >= 0 else "top", fontsize=8.2,
            )
    fig.suptitle("三批互不重叠 test variation 的复现方向", x=0.06, ha="left",
                 fontsize=14, fontweight="bold")
    fig.text(0.06, 0.01, "误差线为任务聚类 Bootstrap 95% CI（20,000 次）。", fontsize=8.7, color="#64748B")
    fig.tight_layout(rect=(0, 0.05, 1, 0.92), w_pad=2.2)
    save(fig, FIGURE_DIR / "scienceworld_v11b_replication.png")


def main():
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    style()
    summary = read_json(ANALYSIS_DIR / "analysis_summary.json")
    core_metrics(summary)
    quality_cost_frontier(summary)
    task_heatmap(read_csv(ANALYSIS_DIR / "task_summary.csv"))
    replication_figure()
    print(json.dumps({"figures": sorted(str(path) for path in FIGURE_DIR.glob("*.png"))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
