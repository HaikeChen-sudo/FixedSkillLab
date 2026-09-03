"""Create the three static figures used in the frozen ALFWorld report."""

import argparse
import json
from pathlib import Path

from result_utils import deduplicate_records
from summarize_results import summarize_by_repeat


LABELS = {
    "no_skill": "No Skill",
    "all_skills": "All Skills",
    "flat_retrieval": "Flat Retrieval",
    "body_aware_retrieval": "Body-aware",
    "bm25_body_retrieval": "BM25 Body",
    "oracle_skill": "Oracle Skill",
}
ORDER = ("no_skill", "body_aware_retrieval", "bm25_body_retrieval", "oracle_skill", "all_skills")
COLORS = {
    "no_skill": "#527A9B",
    "flat_retrieval": "#C9823E",
    "body_aware_retrieval": "#7D9270",
    "bm25_body_retrieval": "#C9823E",
    "oracle_skill": "#315B7D",
    "all_skills": "#765A8C",
}


def plot_rows(records):
    """Return repeat-level means and standard deviations in a stable chart order."""
    summaries = {row["condition"]: row for row in summarize_by_repeat(records)}
    return [
        {
            "condition": condition,
            "label": LABELS[condition],
            "color": COLORS[condition],
            **{metric: summaries[condition][metric] for metric in (
                "task_success_rate", "average_total_tokens", "cost_per_successful_task_usd",
            )},
        }
        for condition in ORDER if condition in summaries
    ]


def failure_matrix(records):
    task_ids = sorted({row["task_id"] for row in records if not row["success"]})
    return task_ids, [
        [sum(not row["success"] for row in records if row["task_id"] == task_id and row["condition"] == condition) for condition in ORDER]
        for task_id in task_ids
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Draw ALFWorld success, token, and cost-quality figures")
    parser.add_argument("results", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("results/figures"))
    parser.add_argument("--deduplicate", action="store_true")
    args = parser.parse_args()
    records = [json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = [row for row in records if row.get("run_id") == args.run_id]
    if not records:
        parser.error("run ID was not found")
    if args.deduplicate:
        records, _ = deduplicate_records(records)
    rows = plot_rows(records)

    import matplotlib.pyplot as plt

    args.output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})

    labels = [row["label"] for row in rows]
    colors = [row["color"] for row in rows]
    summaries = {row["condition"]: row for row in summarize_by_repeat(records)}

    def bars(ax, values, errors, ylabel, title, value_format):
        bars = ax.bar(labels, values, yerr=errors, capsize=4, color=colors, edgecolor="#243447", linewidth=0.7)
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc="left", fontweight="bold", fontsize=11)
        ax.grid(axis="y", color="#D9DEE3", linewidth=0.7)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", rotation=15)
        for bar, value in zip(bars, values):
            ax.annotate(value_format(value), (bar.get_x() + bar.get_width() / 2, value), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=8)

    metrics = [
        ("task_success_rate", 100, "Task success rate (%)", "Task success rate", lambda value: f"{value:.1f}%"),
        ("average_total_tokens", 1 / 1000, "Average total tokens (thousands)", "Inference tokens per episode", lambda value: f"{value:.1f}k"),
        ("average_latency_ms", 1 / 1000, "End-to-end latency (seconds)", "End-to-end latency", lambda value: f"{value:.1f}s"),
        ("cost_per_successful_task_usd", 1000, "Cost per successful task (USD × 10⁻³)", "Cost per successful task", lambda value: f"{value:.3f}"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(10.4, 7.0))
    for axis, (metric, scale, ylabel, title, formatter) in zip(axes.flat, metrics):
        values = [summaries[row["condition"]][metric]["mean"] * scale for row in rows]
        errors = [summaries[row["condition"]][metric]["std"] * scale for row in rows]
        bars(axis, values, errors, ylabel, title, formatter)
    fig.suptitle("ALFWorld condition profile (mean ± sample std, 3 repeats)", x=0.01, ha="left", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(args.output_dir / "alfworld_method_profile.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    label_offsets = {
        "no_skill": (6, 6),
        "body_aware_retrieval": (6, 8),
        "oracle_skill": (6, -18),
        "bm25_body_retrieval": (6, 6),
        "all_skills": (6, 6),
    }
    for row in rows:
        cost = row["cost_per_successful_task_usd"]["mean"] * 1000
        cost_std = row["cost_per_successful_task_usd"]["std"] * 1000
        rate = row["task_success_rate"]["mean"] * 100
        rate_std = row["task_success_rate"]["std"] * 100
        ax.errorbar(cost, rate, xerr=cost_std, yerr=rate_std, fmt="o", color=row["color"], markersize=8, capsize=3)
        ax.annotate(row["label"], (cost, rate), xytext=label_offsets[row["condition"]], textcoords="offset points")
    no_skill = next(row for row in rows if row["condition"] == "no_skill")
    ax.annotate("Pareto-efficient", (
        no_skill["cost_per_successful_task_usd"]["mean"] * 1000,
        no_skill["task_success_rate"]["mean"] * 100,
    ), xytext=(24, -24), textcoords="offset points", color="#243447", fontsize=9,
        arrowprops={"arrowstyle": "->", "color": "#243447", "lw": 0.8})
    ax.set_xlabel("Cost per successful task (USD × 10⁻³)")
    ax.set_ylabel("Task success rate (%)")
    ax.set_title("Quality-cost comparison (mean ± sample std, 3 repeats)", loc="left", fontweight="bold")
    ax.grid(color="#D9DEE3", linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(args.output_dir / "alfworld_quality_cost_frontier.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    task_ids, matrix = failure_matrix(records)
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    image = ax.imshow(matrix, cmap="YlOrRd", vmin=0, vmax=3, aspect="auto")
    ax.set_xticks(range(len(rows)), labels)
    ax.set_yticks(range(len(task_ids)), [task_id.rsplit(":", 1)[-1] for task_id in task_ids])
    ax.set_xlabel("Condition")
    ax.set_ylabel("Failed task ID")
    ax.set_title("Failure count by task and condition (3 repeats)", loc="left", fontweight="bold")
    for row_index, row_values in enumerate(matrix):
        for column_index, value in enumerate(row_values):
            ax.text(column_index, row_index, str(value), ha="center", va="center", color="#1B1B1B" if value < 2 else "white", fontweight="bold")
    colorbar = fig.colorbar(image, ax=ax, pad=0.02)
    colorbar.set_label("Failed episodes")
    fig.tight_layout()
    fig.savefig(args.output_dir / "alfworld_failure_heatmap.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    families = (
        "heat_then_place", "clean_then_place", "cool_then_place",
        "two_object_place", "light_inspection", "simple_pick_place",
    )
    family_labels = ("Heat", "Clean", "Cool", "Two objects", "Light", "Simple place")
    family_matrix = []
    for condition in [row["condition"] for row in rows]:
        family_matrix.append([
            100 * sum(item["success"] for item in records if item["condition"] == condition and item.get("task_family") == family)
            / sum(1 for item in records if item["condition"] == condition and item.get("task_family") == family)
            for family in families
        ])
    fig, ax = plt.subplots(figsize=(9.0, 4.2))
    image = ax.imshow(family_matrix, cmap="Blues", vmin=75, vmax=100, aspect="auto")
    ax.set_xticks(range(len(families)), family_labels)
    ax.set_yticks(range(len(rows)), labels)
    ax.set_xlabel("Task family")
    ax.set_ylabel("Condition")
    ax.set_title("Task success rate by family", loc="left", fontweight="bold")
    for row_index, values in enumerate(family_matrix):
        for column_index, value in enumerate(values):
            ax.text(column_index, row_index, f"{value:.1f}%", ha="center", va="center",
                    color="white" if value < 87 else "#1B1B1B", fontsize=8, fontweight="bold")
    colorbar = fig.colorbar(image, ax=ax, pad=0.02)
    colorbar.set_label("Task success rate (%)")
    fig.tight_layout()
    fig.savefig(args.output_dir / "alfworld_family_success_heatmap.png", dpi=220, bbox_inches="tight")
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
