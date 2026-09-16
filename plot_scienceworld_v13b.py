"""Create colored figures for the ScienceWorld v13b Markdown report."""

import csv
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from plot_alfworld_v7 import save, style


ROOT = Path(__file__).resolve().parent
ANALYSIS_DIR = ROOT / "results" / "formal_scienceworld_v13b"
FIGURE_DIR = ANALYSIS_DIR / "figures"
ORDER = ("oracle_v3_full", "oracle_v3_metadata", "oracle_v3_placebo")
LABELS = {
    "oracle_v3_full": "完整 Procedure",
    "oracle_v3_metadata": "仅 Metadata",
    "oracle_v3_placebo": "等词数 Placebo",
}
SHORT_LABELS = {
    "oracle_v3_full": "Full",
    "oracle_v3_metadata": "Metadata",
    "oracle_v3_placebo": "Placebo",
}
COLORS = {
    "oracle_v3_full": "#2563EB",
    "oracle_v3_metadata": "#D97706",
    "oracle_v3_placebo": "#64748B",
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
        ("task_success_rate", "任务成功率 ↑", 100, lambda value: f"{value:.1f}%"),
        ("average_input_tokens", "Input Tokens ↓", 1e-6, lambda value: f"{value:.2f}M"),
        ("average_output_tokens", "Output Tokens ↓", 1e-3, lambda value: f"{value:.1f}k"),
        ("average_total_tokens", "Total Tokens ↓", 1e-6, lambda value: f"{value:.2f}M"),
        ("average_latency_ms", "端到端延迟 ↓", 1e-3, lambda value: f"{value:.1f}s"),
        ("cost_per_successful_task_usd", "单次成功成本 ↓", 1, lambda value: f"${value:.4f}"),
    )
    fig, axes = plt.subplots(2, 3, figsize=(12.6, 7.0))
    for ax, (field, title, scale, formatter) in zip(axes.flat, specs):
        values = [repeats[name][field]["mean"] * scale for name in ORDER]
        errors = [repeats[name][field]["std"] * scale for name in ORDER]
        bars = ax.bar(
            range(3), values, yerr=errors, capsize=4, width=0.62,
            color=[COLORS[name] for name in ORDER], edgecolor="#334155", linewidth=0.5,
        )
        ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
        ax.set_xticks(range(3), [SHORT_LABELS[name] for name in ORDER], fontsize=8.5)
        ax.grid(axis="y", color="#E2E8F0", linewidth=0.7)
        ax.set_axisbelow(True)
        ax.set_ylim(bottom=0)
        ax.margins(y=0.30)
        for bar, value, error in zip(bars, values, errors):
            ax.text(
                bar.get_x() + bar.get_width() / 2, value + error,
                formatter(value), ha="center", va="bottom", fontsize=8,
            )
    fig.suptitle(
        "ScienceWorld v13b：完整 Procedure 同时提高成功率并压缩推理开销",
        x=0.055, ha="left", fontsize=14.2, fontweight="bold",
    )
    fig.text(
        0.055, 0.012,
        "6 道状态转换任务 × 3 条件 × 3 次重复；柱高为重复均值，误差线为重复间样本标准差。",
        fontsize=8.8, color="#64748B",
    )
    fig.tight_layout(rect=(0, 0.055, 1, 0.94), w_pad=1.5, h_pad=1.9)
    save(fig, FIGURE_DIR / "scienceworld_v13b_core_metrics.png")


def paired_effects(rows):
    lookup = {(row["baseline"], row["condition"]): row for row in rows}
    controls = ("oracle_v3_metadata", "oracle_v3_placebo")
    success, success_low, success_high = [], [], []
    tokens, token_low, token_high = [], [], []
    for control in controls:
        row = lookup[("oracle_v3_full", control)]
        success.append(-100 * float(row["success_rate_difference"]))
        success_low.append(-100 * float(row["task_cluster_bootstrap_ci_high"]))
        success_high.append(-100 * float(row["task_cluster_bootstrap_ci_low"]))
        tokens.append(float(row["average_total_tokens_difference"]) / 1e6)
        token_low.append(float(row["total_tokens_cluster_bootstrap_ci_low"]) / 1e6)
        token_high.append(float(row["total_tokens_cluster_bootstrap_ci_high"]) / 1e6)

    labels = ("Full − Metadata", "Full − Placebo")
    colors = (COLORS["oracle_v3_metadata"], COLORS["oracle_v3_placebo"])
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.4))
    panels = (
        (success, success_low, success_high, "完整 Procedure 的成功率优势", "百分点"),
        (tokens, token_low, token_high, "完整 Procedure 节省的 Total Tokens", "百万 Token"),
    )
    for ax, (values, lows, highs, title, ylabel) in zip(axes, panels):
        yerr = np.array([
            [value - low for value, low in zip(values, lows)],
            [high - value for value, high in zip(values, highs)],
        ])
        bars = ax.bar(range(2), values, yerr=yerr, capsize=5, width=0.58,
                      color=colors, edgecolor="#334155", linewidth=0.5)
        ax.axhline(0, color="#475569", linewidth=0.9)
        ax.set_xticks(range(2), labels, fontsize=9)
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc="left", fontsize=11.5, fontweight="bold")
        ax.grid(axis="y", color="#E2E8F0", linewidth=0.7)
        ax.set_axisbelow(True)
        for bar, value, high in zip(bars, values, highs):
            suffix = " pp" if ylabel == "百分点" else "M"
            ax.text(bar.get_x() + bar.get_width() / 2, high,
                    f"{value:.1f}{suffix}" if ylabel == "百分点" else f"{value:.2f}{suffix}",
                    ha="center", va="bottom", fontsize=8.5)
    fig.suptitle("任务簇配对效应", x=0.06, ha="left", fontsize=14, fontweight="bold")
    fig.text(0.06, 0.01, "误差线为 6 个任务簇 Bootstrap 95% CI（20,000 次）。", fontsize=8.7, color="#64748B")
    fig.tight_layout(rect=(0, 0.05, 1, 0.92), w_pad=2.1)
    save(fig, FIGURE_DIR / "scienceworld_v13b_paired_effects.png")


def task_heatmap(rows):
    task_ids = list(dict.fromkeys(row["task_id"] for row in rows))
    lookup = {(row["task_id"], row["condition"]): int(row["successes"]) for row in rows}
    matrix = np.array([[lookup[(task, condition)] for task in task_ids] for condition in ORDER])
    labels = [item.replace(":v", "\nv") for item in task_ids]
    fig, ax = plt.subplots(figsize=(8.8, 3.5))
    image = ax.imshow(matrix, vmin=0, vmax=3, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(task_ids)), labels, fontsize=9)
    ax.set_yticks(range(3), [LABELS[name] for name in ORDER], fontsize=9.5)
    for row_index in range(3):
        for column_index in range(len(task_ids)):
            value = matrix[row_index, column_index]
            ax.text(column_index, row_index, f"{value}/3", ha="center", va="center",
                    fontsize=9, color="white" if value >= 2 else "#0F172A")
    ax.axvline(2.5, color="white", linewidth=2.2)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.035, pad=0.025, ticks=(0, 1, 2, 3))
    colorbar.set_label("三次重复中的成功次数", fontsize=8.5)
    ax.set_title("逐任务成功次数", loc="left", fontsize=13.5, fontweight="bold")
    fig.tight_layout()
    save(fig, FIGURE_DIR / "scienceworld_v13b_task_success.png")


def quality_cost(summary):
    repeats = repeat_lookup(summary)
    offsets = {
        "oracle_v3_full": (9, 8),
        "oracle_v3_metadata": (9, -18),
        "oracle_v3_placebo": (-98, 8),
    }
    markers = {"oracle_v3_full": "D", "oracle_v3_metadata": "s", "oracle_v3_placebo": "o"}
    fig, ax = plt.subplots(figsize=(7.8, 4.9))
    for name in ORDER:
        row = repeats[name]
        x = row["cost_per_successful_task_usd"]["mean"]
        y = 100 * row["task_success_rate"]["mean"]
        ax.errorbar(
            x, y, xerr=row["cost_per_successful_task_usd"]["std"],
            yerr=100 * row["task_success_rate"]["std"], fmt=markers[name], markersize=10,
            color=COLORS[name], ecolor=COLORS[name], elinewidth=1.2, capsize=4,
            markeredgecolor="#0F172A", markeredgewidth=0.7, zorder=3,
        )
        ax.annotate(LABELS[name], (x, y), xytext=offsets[name], textcoords="offset points", fontsize=9.5)
    ax.annotate("理想方向", xy=(0.006, 82), xytext=(0.021, 55),
                arrowprops={"arrowstyle": "->", "color": "#475569"}, color="#475569", fontsize=9)
    ax.set_xlabel("单次成功成本 (USD)  →")
    ax.set_ylabel("任务成功率 (%)  ↑")
    ax.set_title("质量—成本位置", loc="left", fontsize=13.5, fontweight="bold")
    ax.grid(color="#E2E8F0", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.set_xlim(left=0)
    ax.set_ylim(20, 92)
    fig.text(0.13, 0.01, "点与误差线为 3 次重复的均值和样本标准差。", fontsize=8.6, color="#64748B")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, FIGURE_DIR / "scienceworld_v13b_quality_cost.png")


def main():
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    style()
    summary = read_json(ANALYSIS_DIR / "analysis_summary.json")
    core_metrics(summary)
    paired_effects(read_csv(ANALYSIS_DIR / "paired_statistics.csv"))
    task_heatmap(read_csv(ANALYSIS_DIR / "task_summary.csv"))
    quality_cost(summary)
    print(json.dumps({"figures": sorted(str(path) for path in FIGURE_DIR.glob("*.png"))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
