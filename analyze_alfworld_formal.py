"""Freeze and analyze one completed paired ALFWorld experiment."""

import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

from result_utils import deduplicate_records
from summarize_results import episode_metrics, summarize_by_repeat


CONDITIONS = (
    "no_skill",
    "all_skills",
    "body_aware_retrieval",
    "bm25_body_retrieval",
    "oracle_skill",
)
LABELS = {
    "no_skill": "No Skill",
    "all_skills": "All Skills",
    "body_aware_retrieval": "Body-aware",
    "bm25_body_retrieval": "BM25 Body",
    "oracle_skill": "Oracle Skill",
}


def primary_gold_rank(row):
    if "primary_gold_skill_rank" in row:
        return row["primary_gold_skill_rank"]
    ranks = row.get("gold_skill_ranks", [])
    return ranks[1] if len(ranks) > 1 else None


def percentile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def cluster_bootstrap(records, metric, iterations=20000, seed=20260901):
    """Resample tasks, keeping all three repeats together."""
    tasks = defaultdict(list)
    for row in records:
        tasks[row["task_id"]].append(row)
    task_ids = sorted(tasks)
    rng = random.Random(seed)
    estimates = []
    for _ in range(iterations):
        sample = [row for _ in task_ids for row in tasks[rng.choice(task_ids)]]
        estimates.append(metric(sample))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def paired_bootstrap(records, condition, baseline="no_skill", iterations=20000, seed=20260901):
    paired = defaultdict(dict)
    for row in records:
        if row["condition"] in {condition, baseline}:
            paired[row["task_id"]][(row["condition"], row["repeat"])] = int(row["success"])
    task_ids = sorted(paired)
    task_differences = []
    for task_id in task_ids:
        values = paired[task_id]
        differences = [values[(condition, repeat)] - values[(baseline, repeat)] for repeat in range(3)]
        task_differences.append(mean(differences))
    rng = random.Random(seed)
    samples = [mean(rng.choice(task_differences) for _ in task_ids) for _ in range(iterations)]
    p_value = min(1.0, 2 * min(sum(value <= 0 for value in samples), sum(value >= 0 for value in samples)) / iterations)
    return {
        "condition": condition,
        "baseline": baseline,
        "difference": mean(task_differences),
        "ci_low": percentile(samples, 0.025),
        "ci_high": percentile(samples, 0.975),
        "bootstrap_p_value": p_value,
    }


def failure_category(row, lookup):
    key = (row["task_id"], row["repeat"])
    no_skill_success = lookup[(key, "no_skill")]["success"]
    oracle_success = lookup[(key, "oracle_skill")]["success"]
    selective = row["condition"] in {"body_aware_retrieval", "bm25_body_retrieval"}
    if selective and primary_gold_rank(row) is None and oracle_success:
        return "routing_error"
    if row["condition"] != "no_skill" and no_skill_success:
        return "skill_condition_interference"
    if not no_skill_success and not oracle_success:
        return "shared_execution_error"
    if row["steps"] >= 50:
        return "step_budget_exhausted"
    return "execution_error_other"


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Analyze a completed 30-task x 5-condition x 3-repeat ALFWorld run")
    parser.add_argument("results", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("results/formal"))
    args = parser.parse_args()

    records = [json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = [row for row in records if row.get("run_id") == args.run_id]
    records, duplicates = deduplicate_records(records)
    counts = Counter(row["condition"] for row in records)
    if duplicates or len(records) != 450 or any(counts[condition] != 90 for condition in CONDITIONS):
        parser.error(f"expected 450 unique records and 90 per condition; got {len(records)}, duplicates={duplicates}, counts={dict(counts)}")

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    frozen = output / f"{args.run_id}.jsonl"
    ordered = sorted(records, key=lambda row: (row["task_index"], row["repeat"], CONDITIONS.index(row["condition"])))
    frozen.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in ordered), encoding="utf-8")
    digest = hashlib.sha256(frozen.read_bytes()).hexdigest()

    repeat = {row["condition"]: row for row in summarize_by_repeat(records)}
    summary_rows = []
    for condition in CONDITIONS:
        rows = [row for row in records if row["condition"] == condition]
        metrics = episode_metrics(rows)
        ci_low, ci_high = cluster_bootstrap(rows, lambda sample: mean(int(row["success"]) for row in sample))
        summary_rows.append({
            "condition": condition,
            "label": LABELS[condition],
            "episodes": len(rows),
            "successes": sum(row["success"] for row in rows),
            "task_success_rate": metrics["task_success_rate"],
            "success_rate_repeat_std": repeat[condition]["task_success_rate"]["std"],
            "success_ci_low": ci_low,
            "success_ci_high": ci_high,
            **{name: metrics[name] for name in (
                "average_input_tokens", "average_output_tokens", "average_total_tokens",
                "average_latency_ms", "cost_per_successful_task_usd", "average_tool_calls",
                "efficiency_per_1k_tokens",
            )},
        })
    summary_fields = list(summary_rows[0])
    write_csv(output / "condition_summary.csv", summary_rows, summary_fields)

    paired_rows = [paired_bootstrap(records, condition) for condition in CONDITIONS if condition != "no_skill"]
    write_csv(output / "paired_comparisons.csv", paired_rows, list(paired_rows[0]))

    family_rows = []
    grouped = defaultdict(list)
    for row in records:
        grouped[(row["condition"], row["task_family"])].append(row)
    for (condition, family), rows in sorted(grouped.items(), key=lambda item: (CONDITIONS.index(item[0][0]), item[0][1])):
        metrics = episode_metrics(rows)
        family_rows.append({"condition": condition, "label": LABELS[condition], "task_family": family, "episodes": len(rows), **metrics})
    write_csv(output / "family_summary.csv", family_rows, list(family_rows[0]))

    lookup = {((row["task_id"], row["repeat"]), row["condition"]): row for row in records}
    failure_rows = []
    for row in records:
        if row["success"]:
            continue
        rejected = sum(not step["result"].get("ok", True) for step in row["trace"])
        failure_rows.append({
            "condition": row["condition"],
            "task_id": row["task_id"],
            "task_family": row["task_family"],
            "repeat": row["repeat"],
            "category": failure_category(row, lookup),
            "steps": row["steps"],
            "rejected_actions": rejected,
            "primary_gold_skill_rank": primary_gold_rank(row),
            "skills_loaded": row.get("skills_loaded", []),
            "gold_skills": row.get("gold_skills", []),
            "last_actions": [step.get("command") for step in row["trace"][-8:]],
        })
    (output / "failures.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in failure_rows), encoding="utf-8")
    taxonomy = Counter(row["category"] for row in failure_rows)
    taxonomy_rows = [{"category": category, "failures": count, "share": count / len(failure_rows)} for category, count in sorted(taxonomy.items())]
    write_csv(output / "failure_taxonomy.csv", taxonomy_rows, ["category", "failures", "share"])

    bm25 = [row for row in records if row["condition"] == "bm25_body_retrieval"]
    unique_bm25 = {row["task_id"]: primary_gold_rank(row) for row in bm25}
    retrieval_audit = {
        "episodes": len(bm25),
        "primary_gold_hit_at_3_episodes": sum(primary_gold_rank(row) is not None for row in bm25),
        "primary_gold_hit_at_3_episode_rate": mean(primary_gold_rank(row) is not None for row in bm25),
        "unique_tasks": len({row["task_id"] for row in bm25}),
        "primary_gold_hit_at_3_tasks": sum(rank is not None for rank in unique_bm25.values()),
        "primary_gold_hit_at_3_task_rate": mean(rank is not None for rank in unique_bm25.values()),
        "success_when_hit": mean(row["success"] for row in bm25 if primary_gold_rank(row) is not None),
        "success_when_missed": mean(row["success"] for row in bm25 if primary_gold_rank(row) is None),
    }
    task_ids = {row["task_id"] for row in records}
    task_family = {row["task_id"]: row["task_family"] for row in records}
    validation = {
        "unique_episode_keys": len({(row["task_id"], row["condition"], row["repeat"]) for row in records}),
        "expected_episode_keys": 450,
        "task_count": len(task_ids),
        "family_task_counts": dict(sorted(Counter(task_family.values()).items())),
        "condition_episode_counts": {condition: counts[condition] for condition in CONDITIONS},
        "repeat_values": sorted({row["repeat"] for row in records}),
        "models": sorted({row["model"] for row in records}),
        "temperatures": sorted({row["temperature"] for row in records}),
        "agent_protocol_versions": sorted({row.get("agent_protocol_version") for row in records}),
        "skill_library_sha256_values": sorted({row.get("skill_library_sha256") for row in records}),
        "missing_success_values": sum(row.get("success") is None for row in records),
    }
    manifest = {
        "run_id": args.run_id,
        "records": len(records),
        "tasks": len({row["task_id"] for row in records}),
        "conditions": list(CONDITIONS),
        "repeats": 3,
        "frozen_file": str(frozen),
        "sha256": digest,
        "source_file": str(args.results),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "analysis_summary.json").write_text(json.dumps({
        "manifest": manifest,
        "condition_summary": summary_rows,
        "paired_comparisons": paired_rows,
        "failure_taxonomy": taxonomy_rows,
        "retrieval_audit": retrieval_audit,
        "validation": validation,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(output), "sha256": digest, "failures": len(failure_rows), **retrieval_audit}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
