"""Validate, freeze, and summarize one completed ScienceWorld experiment."""

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from result_utils import deduplicate_records
from scienceworld_suites import SUITES
from summarize_results import episode_metrics, summarize_by_repeat


LABELS = {
    "no_skill": "No Skill",
    "all_skills": "All Skills",
    "flat_retrieval": "Flat Retrieval",
    "body_aware_retrieval": "Body-aware Retrieval",
    "oracle_skill": "Oracle v1",
    "oracle_v2": "Oracle v2",
    "oracle_v3": "Oracle v3",
}
METRICS = (
    "average_input_tokens",
    "average_output_tokens",
    "average_total_tokens",
    "average_latency_ms",
    "cost_per_successful_task_usd",
    "average_tool_calls",
    "efficiency_per_1k_tokens",
    "average_score",
    "average_environment_moves",
)


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def episode_key(row):
    return row["task_name"], row["variation"], row["condition"], row["repeat"]


def percentile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def exact_sign_p_value(positive, negative):
    discordant = positive + negative
    if not discordant:
        return 1.0
    tail = sum(math.comb(discordant, value) for value in range(min(positive, negative) + 1))
    return min(1.0, 2 * tail / 2 ** discordant)


def paired_statistics(records, tasks, conditions, repeats, iterations=20000, seed=20260914):
    baseline = conditions[0]
    lookup = {episode_key(row): row for row in records}
    output = []
    for offset, condition in enumerate(conditions[1:]):
        task_differences = []
        condition_only = baseline_only = 0
        for task, variation in tasks:
            differences = []
            for repeat in range(repeats):
                base_success = bool(lookup[(task, variation, baseline, repeat)]["success"])
                condition_success = bool(lookup[(task, variation, condition, repeat)]["success"])
                condition_only += condition_success and not base_success
                baseline_only += base_success and not condition_success
                differences.append(int(condition_success) - int(base_success))
            task_differences.append(mean(differences))
        rng = random.Random(seed + offset)
        samples = [mean(rng.choice(task_differences) for _ in tasks) for _ in range(iterations)]
        positive = sum(value > 0 for value in task_differences)
        negative = sum(value < 0 for value in task_differences)
        output.append({
            "condition": condition,
            "baseline": baseline,
            "success_rate_difference": mean(task_differences),
            "task_cluster_bootstrap_ci_low": percentile(samples, 0.025),
            "task_cluster_bootstrap_ci_high": percentile(samples, 0.975),
            "condition_only_successes": condition_only,
            "baseline_only_successes": baseline_only,
            "exact_mcnemar_p_value": exact_sign_p_value(condition_only, baseline_only),
            "tasks_positive": positive,
            "tasks_negative": negative,
            "tasks_tied": len(tasks) - positive - negative,
            "exact_task_sign_p_value": exact_sign_p_value(positive, negative),
        })
    return output


def validation_errors(records, suite, conditions, repeats, duplicates=0):
    expected = {
        (task, variation, condition, repeat)
        for task, variation in SUITES[suite]
        for condition in conditions
        for repeat in range(repeats)
    }
    actual = {episode_key(row) for row in records}
    errors = []
    if duplicates:
        errors.append(f"duplicate episode keys: {duplicates}")
    if expected - actual:
        errors.append(f"missing episode keys: {sorted(expected - actual)}")
    if actual - expected:
        errors.append(f"unexpected episode keys: {sorted(actual - expected)}")
    return errors


def failure_category(row):
    if row.get("done") and row.get("environment_moves", 0) >= row.get("max_steps", 100):
        return "environment_move_budget_exhausted"
    if not row.get("done") and row.get("final_text"):
        return "premature_model_stop"
    return "execution_error_other"


def main():
    parser = argparse.ArgumentParser(description="Freeze a completed ScienceWorld run after exact-key validation")
    parser.add_argument("results", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--suite", choices=sorted(SUITES), required=True)
    parser.add_argument("--conditions", required=True)
    parser.add_argument("--repeats", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--purpose", default="held-out evaluation")
    args = parser.parse_args()
    conditions = tuple(args.conditions.split(","))

    loaded = [
        json.loads(line)
        for line in args.results.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("run_id") == args.run_id
    ]
    records, duplicates = deduplicate_records(loaded)
    errors = validation_errors(records, args.suite, conditions, args.repeats, duplicates)
    if errors:
        parser.error("; ".join(errors))

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    case_order = {case: index for index, case in enumerate(SUITES[args.suite])}
    condition_order = {condition: index for index, condition in enumerate(conditions)}
    records.sort(key=lambda row: (
        case_order[(row["task_name"], row["variation"])],
        row["repeat"],
        condition_order[row["condition"]],
    ))
    frozen = output / f"{args.run_id}.jsonl"
    frozen.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in records), encoding="utf-8")
    digest = hashlib.sha256(frozen.read_bytes()).hexdigest()

    repeat_stats = {row["condition"]: row for row in summarize_by_repeat(records)}
    condition_rows = []
    for condition in conditions:
        rows = [row for row in records if row["condition"] == condition]
        metrics = episode_metrics(rows)
        condition_rows.append({
            "condition": condition,
            "label": LABELS.get(condition, condition),
            "episodes": len(rows),
            "successes": sum(row["success"] for row in rows),
            "task_success_rate": metrics["task_success_rate"],
            "task_success_rate_repeat_std": repeat_stats[condition]["task_success_rate"]["std"],
            **{metric: metrics.get(metric) for metric in METRICS},
        })
    write_csv(output / "condition_summary.csv", condition_rows)

    task_rows = []
    for task_name, variation in SUITES[args.suite]:
        for condition in conditions:
            rows = [row for row in records if row["task_name"] == task_name and row["variation"] == variation and row["condition"] == condition]
            metrics = episode_metrics(rows)
            task_rows.append({
                "task_id": f"{task_name}:v{variation:03d}",
                "task_name": task_name,
                "variation": variation,
                "condition": condition,
                "episodes": len(rows),
                "successes": sum(row["success"] for row in rows),
                "task_success_rate": metrics["task_success_rate"],
                **{metric: metrics.get(metric) for metric in METRICS},
            })
    write_csv(output / "task_summary.csv", task_rows)

    lookup = {episode_key(row): row for row in records}
    paired_rows = []
    baseline = conditions[0]
    for task_name, variation in SUITES[args.suite]:
        for repeat in range(args.repeats):
            base = lookup[(task_name, variation, baseline, repeat)]
            for condition in conditions[1:]:
                compared = lookup[(task_name, variation, condition, repeat)]
                outcome = {
                    (True, True): "both_success",
                    (True, False): "baseline_only",
                    (False, True): "condition_only",
                    (False, False): "both_fail",
                }[(base["success"], compared["success"])]
                paired_rows.append({
                    "task_id": base["task_id"],
                    "repeat": repeat,
                    "baseline": baseline,
                    "condition": condition,
                    "outcome": outcome,
                    "success_difference": int(compared["success"]) - int(base["success"]),
                    "score_difference": compared["score"] - base["score"],
                    "total_tokens_difference": compared["total_tokens"] - base["total_tokens"],
                    "latency_ms_difference": compared["latency_ms"] - base["latency_ms"],
                    "cost_usd_difference": compared["cost_usd"] - base["cost_usd"],
                    "tool_calls_difference": compared["tool_calls"] - base["tool_calls"],
                })
    write_csv(output / "paired_comparisons.csv", paired_rows)
    paired_stats = paired_statistics(records, SUITES[args.suite], conditions, args.repeats)
    write_csv(output / "paired_statistics.csv", paired_stats)

    failures = []
    for row in records:
        if row["success"]:
            continue
        failures.append({
            "task_id": row["task_id"],
            "condition": row["condition"],
            "repeat": row["repeat"],
            "category": failure_category(row),
            "score": row["score"],
            "done": row["done"],
            "tool_calls": row["tool_calls"],
            "environment_moves": row["environment_moves"],
            "rejected_actions": sum(not step.get("result", {}).get("ok", False) for step in row["trace"]),
            "last_actions": [step.get("command") for step in row["trace"][-8:]],
            "final_text": row.get("final_text", ""),
        })
    (output / "failures.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in failures), encoding="utf-8")
    taxonomy = Counter(row["category"] for row in failures)
    write_csv(output / "failure_taxonomy.csv", [
        {"category": category, "failures": count, "share": count / len(failures)}
        for category, count in sorted(taxonomy.items())
    ])

    retrieval_rows = []
    for condition in conditions:
        selected = [row for row in records if row["condition"] == condition and row.get("retriever")]
        if not selected:
            continue
        hits = [row for row in selected if row.get("retrieval_rank") is not None]
        misses = [row for row in selected if row.get("retrieval_rank") is None]
        retrieval_rows.append({
            "condition": condition,
            "episodes": len(selected),
            "gold_hit_at_3": len(hits),
            "gold_hit_at_3_rate": len(hits) / len(selected),
            "success_rate_when_hit": sum(row["success"] for row in hits) / len(hits) if hits else None,
            "success_rate_when_missed": sum(row["success"] for row in misses) / len(misses) if misses else None,
            "missed_tasks": ",".join(row["task_id"] for row in misses),
        })
    write_csv(output / "retrieval_summary.csv", retrieval_rows)

    manifest = {
        "run_id": args.run_id,
        "purpose": args.purpose,
        "records": len(records),
        "tasks": len(SUITES[args.suite]),
        "conditions": list(conditions),
        "repeats": args.repeats,
        "suite": args.suite,
        "frozen_file": str(frozen),
        "sha256": digest,
        "source_file": str(args.results),
        "models": sorted({row["model"] for row in records}),
        "temperatures": sorted({row["temperature"] for row in records}),
        "agent_protocol_versions": sorted({row["agent_protocol_version"] for row in records}),
        "skill_library_versions": sorted({str(row.get("skill_library_version")) for row in records}),
        "success_rule": "environment score >= 100",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "analysis_summary.json").write_text(json.dumps({
        "manifest": manifest,
        "condition_summary": condition_rows,
        "repeat_statistics": [repeat_stats[condition] for condition in conditions],
        "paired_outcomes": dict(sorted(Counter(row["outcome"] for row in paired_rows).items())),
        "paired_statistics": paired_stats,
        "retrieval_summary": retrieval_rows,
        "failure_taxonomy": dict(sorted(taxonomy.items())),
        "validation": {
            "records_loaded": len(loaded),
            "records_kept": len(records),
            "duplicates_removed": duplicates,
            "unique_episode_keys": len({episode_key(row) for row in records}),
        },
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output_dir": str(output),
        "records": len(records),
        "duplicates": duplicates,
        "failures": len(failures),
        "sha256": digest,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
