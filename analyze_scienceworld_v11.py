"""Derive v11b sensitivity and cross-batch replication statistics."""

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

from analyze_scienceworld_formal import paired_statistics
from scienceworld_suites import (
    SCIENCEWORLD_V6_ROUTER_FORMAL_12,
    SCIENCEWORLD_V10_CONFIRM_12,
    SCIENCEWORLD_V11B_CONFIRM_18,
)


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "results" / "formal_scienceworld_v11" / "derived_analysis.json"
CONDITIONS = ("no_skill", "body_aware_retrieval")
STUDIES = (
    (
        "v9_discovery",
        ROOT / "results" / "formal_scienceworld_v6" / "scienceworld-v6-router-formal-12x3.jsonl",
        SCIENCEWORLD_V6_ROUTER_FORMAL_12,
    ),
    (
        "v10_confirmation",
        ROOT / "results" / "formal_scienceworld_v10" / "scienceworld-v10-confirm-12x3.jsonl",
        SCIENCEWORLD_V10_CONFIRM_12,
    ),
    (
        "v11b_balanced_confirmation",
        ROOT / "results" / "formal_scienceworld_v11" / "scienceworld-v11b-confirm-18x3.jsonl",
        SCIENCEWORLD_V11B_CONFIRM_18,
    ),
)


def load_selected(path):
    return [
        row
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in [json.loads(line)]
        if row["condition"] in CONDITIONS
    ]


def condition_summary(records, condition):
    rows = [row for row in records if row["condition"] == condition]
    return {
        "episodes": len(rows),
        "successes": sum(bool(row["success"]) for row in rows),
        "task_success_rate": mean(bool(row["success"]) for row in rows),
        "average_total_tokens": mean(row["total_tokens"] for row in rows),
    }


def task_token_pairs(records, tasks):
    grouped = defaultdict(list)
    for row in records:
        grouped[(row["task_name"], row["variation"], row["condition"])].append(row["total_tokens"])
    pairs = []
    for task, variation in tasks:
        baseline = mean(grouped[(task, variation, "no_skill")])
        body = mean(grouped[(task, variation, "body_aware_retrieval")])
        pairs.append({
            "task_id": f"{task}:v{variation:03d}",
            "no_skill_mean_total_tokens": baseline,
            "body_aware_mean_total_tokens": body,
            "difference": body - baseline,
            "relative_change_pct": 100 * (body / baseline - 1),
        })
    return pairs


def v11b_sensitivity(records):
    pairs = task_token_pairs(records, SCIENCEWORLD_V11B_CONFIRM_18)
    leave_one_out = []
    for omitted in pairs:
        kept = [row for row in pairs if row is not omitted]
        baseline = mean(row["no_skill_mean_total_tokens"] for row in kept)
        body = mean(row["body_aware_mean_total_tokens"] for row in kept)
        leave_one_out.append({
            "omitted_task": omitted["task_id"],
            "relative_change_pct": 100 * (body / baseline - 1),
        })
    return {
        "median_task_total_tokens_difference": median(row["difference"] for row in pairs),
        "median_task_relative_change_pct": median(row["relative_change_pct"] for row in pairs),
        "tasks_with_lower_total_tokens": sum(row["difference"] < 0 for row in pairs),
        "tasks_with_higher_total_tokens": sum(row["difference"] > 0 for row in pairs),
        "leave_one_task_out_relative_change_pct_min": min(row["relative_change_pct"] for row in leave_one_out),
        "leave_one_task_out_relative_change_pct_max": max(row["relative_change_pct"] for row in leave_one_out),
        "largest_absolute_reductions": sorted(pairs, key=lambda row: row["difference"])[:6],
    }


def family_summary(records):
    rows = []
    for task_name in dict.fromkeys(task for task, _ in SCIENCEWORLD_V11B_CONFIRM_18):
        for condition in ("no_skill", "flat_retrieval", "body_aware_retrieval"):
            selected = [
                row for row in records
                if row["task_name"] == task_name and row["condition"] == condition
            ]
            rows.append({
                "task_name": task_name,
                "condition": condition,
                "episodes": len(selected),
                "successes": sum(bool(row["success"]) for row in selected),
                "task_success_rate": mean(bool(row["success"]) for row in selected),
                "average_total_tokens": mean(row["total_tokens"] for row in selected),
                "average_environment_moves": mean(row["environment_moves"] for row in selected),
            })
    return rows


def main():
    all_records = []
    all_tasks = []
    batches = []
    compatibility = defaultdict(set)
    for label, path, tasks in STUDIES:
        records = load_selected(path)
        baseline = condition_summary(records, "no_skill")
        body = condition_summary(records, "body_aware_retrieval")
        paired = paired_statistics(records, tasks, CONDITIONS, 3, seed=20260915)[0]
        batches.append({
            "study": label,
            "tasks": len(tasks),
            "episodes_per_condition": baseline["episodes"],
            "no_skill": baseline,
            "body_aware_retrieval": body,
            "success_rate_difference": paired["success_rate_difference"],
            "success_rate_ci": [
                paired["task_cluster_bootstrap_ci_low"],
                paired["task_cluster_bootstrap_ci_high"],
            ],
            "average_total_tokens_difference": paired["average_total_tokens_difference"],
            "total_tokens_difference_ci": [
                paired["total_tokens_cluster_bootstrap_ci_low"],
                paired["total_tokens_cluster_bootstrap_ci_high"],
            ],
            "relative_total_tokens_change_pct": 100 * (
                body["average_total_tokens"] / baseline["average_total_tokens"] - 1
            ),
        })
        for row in records:
            compatibility["models"].add(row["model"])
            compatibility["temperatures"].add(row["temperature"])
            compatibility["agent_protocol_versions"].add(row["agent_protocol_version"])
            compatibility["skill_library_versions"].add(str(row.get("skill_library_version")))
        all_records.extend(records)
        all_tasks.extend(tasks)

    if len(set(all_tasks)) != len(all_tasks):
        raise ValueError("cross-batch task/variation pairs must not overlap")
    v11_all = [
        json.loads(line)
        for line in STUDIES[-1][1].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    output = {
        "scope": "The pooled analysis is exploratory and does not replace the preregistered v11b analysis.",
        "compatibility": {key: sorted(values, key=str) for key, values in compatibility.items()},
        "batches": batches,
        "exploratory_pooled": {
            "tasks": len(all_tasks),
            "episodes_per_condition": len(all_records) // 2,
            "no_skill": condition_summary(all_records, "no_skill"),
            "body_aware_retrieval": condition_summary(all_records, "body_aware_retrieval"),
            "paired_statistics": paired_statistics(
                all_records, all_tasks, CONDITIONS, 3, iterations=50000, seed=20260915
            )[0],
        },
        "v11b_token_sensitivity": v11b_sensitivity(load_selected(STUDIES[-1][1])),
        "v11b_family_summary": family_summary(v11_all),
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "pooled_tasks": len(all_tasks)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
