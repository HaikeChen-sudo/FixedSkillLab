"""Freeze and analyze the v7 ALFWorld development and targeted-test runs."""

import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

from result_utils import deduplicate_records


CONDITIONS = ("no_skill", "oracle_v5", "oracle_v7")
LABELS = {"no_skill": "No Skill", "oracle_v5": "Oracle v5", "oracle_v7": "Oracle v7"}
METRICS = (
    "input_tokens", "output_tokens", "total_tokens", "latency_ms", "cost_usd", "tool_calls"
)


def percentile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows):
    successes = sum(bool(row["success"]) for row in rows)
    total_cost = sum(row.get("cost_usd", 0) for row in rows)
    success_rate = successes / len(rows)
    return {
        "episodes": len(rows),
        "successes": successes,
        "task_success_rate": success_rate,
        "average_input_tokens": mean(row["input_tokens"] for row in rows),
        "average_output_tokens": mean(row["output_tokens"] for row in rows),
        "average_total_tokens": mean(row["total_tokens"] for row in rows),
        "average_latency_ms": mean(row["latency_ms"] for row in rows),
        "cost_per_successful_task_usd": total_cost / successes if successes else None,
        "average_tool_calls": mean(row["tool_calls"] for row in rows),
        "efficiency_per_1k_tokens": success_rate / mean(row["total_tokens"] for row in rows) * 1000,
    }


def cluster_ci(rows, value, iterations=20000, seed=20260907):
    groups = defaultdict(list)
    for row in rows:
        groups[row["task_id"]].append(row)
    task_ids = sorted(groups)
    rng = random.Random(seed)
    estimates = []
    for _ in range(iterations):
        sample = [item for _ in task_ids for item in groups[rng.choice(task_ids)]]
        estimates.append(value(sample))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def paired_comparison(rows, condition, baseline="no_skill", iterations=20000, seed=20260907):
    by_key = {(row["task_id"], row["repeat"], row["condition"]): row for row in rows}
    task_ids = sorted({row["task_id"] for row in rows})
    result = {"condition": condition, "label": LABELS[condition], "baseline": baseline}
    rng = random.Random(seed)
    definitions = {
        "success_rate": lambda row: int(row["success"]),
        "total_tokens": lambda row: row["total_tokens"],
        "latency_ms": lambda row: row["latency_ms"],
        "cost_usd_per_episode": lambda row: row.get("cost_usd", 0),
        "tool_calls": lambda row: row["tool_calls"],
    }
    for name, getter in definitions.items():
        task_differences = []
        for task_id in task_ids:
            repeats = sorted({row["repeat"] for row in rows if row["task_id"] == task_id})
            diffs = [
                getter(by_key[(task_id, repeat, condition)]) - getter(by_key[(task_id, repeat, baseline)])
                for repeat in repeats
            ]
            task_differences.append(mean(diffs))
        samples = [mean(rng.choice(task_differences) for _ in task_ids) for _ in range(iterations)]
        result[f"{name}_difference"] = mean(task_differences)
        result[f"{name}_ci_low"] = percentile(samples, 0.025)
        result[f"{name}_ci_high"] = percentile(samples, 0.975)
        if name == "success_rate":
            result["success_bootstrap_p_value"] = min(
                1.0,
                2 * min(sum(item <= 0 for item in samples), sum(item >= 0 for item in samples)) / iterations,
            )
    return result


def condition_summary(rows):
    output = []
    for condition in CONDITIONS:
        subset = [row for row in rows if row["condition"] == condition]
        metrics = summarize(subset)
        repeat_rates = []
        for repeat in sorted({row["repeat"] for row in subset}):
            repeat_rows = [row for row in subset if row["repeat"] == repeat]
            repeat_rates.append(mean(int(row["success"]) for row in repeat_rows))
        low, high = cluster_ci(subset, lambda sample: mean(int(row["success"]) for row in sample))
        output.append({
            "condition": condition,
            "label": LABELS[condition],
            **metrics,
            "success_rate_repeat_std": stdev(repeat_rates),
            "success_ci_low": low,
            "success_ci_high": high,
        })
    return output


def family_summary(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["condition"], row["task_family"])].append(row)
    output = []
    for condition in CONDITIONS:
        for family in sorted({key[1] for key in grouped if key[0] == condition}):
            subset = grouped[(condition, family)]
            output.append({"condition": condition, "label": LABELS[condition], "task_family": family, **summarize(subset)})
    return output


def task_summary(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["task_id"], row["task_index"], row["task_family"], row["condition"])].append(row)
    output = []
    for (task_id, task_index, family, condition), subset in sorted(grouped.items()):
        output.append({
            "task_id": task_id, "task_index": task_index, "task_family": family,
            "condition": condition, "label": LABELS[condition], **summarize(subset),
        })
    return output


def failure_rows(rows):
    output = []
    for row in rows:
        if row["success"]:
            continue
        commands = [step.get("command", "") for step in row.get("trace", [])]
        query = row.get("retrieval_query", "").lower()
        wrong_noun = "cup" in query and any("mug" in command.lower() for command in commands)
        output.append({
            "condition": row["condition"], "task_id": row["task_id"],
            "task_family": row["task_family"], "repeat": row["repeat"],
            "category": "target_object_confusion" if wrong_noun else "execution_error_other",
            "step_budget_exhausted": row["steps"] >= 100,
            "steps": row["steps"], "total_tokens": row["total_tokens"],
            "goal": row.get("retrieval_query", ""), "last_actions": commands[-8:],
        })
    return output


def load_run(source, run_id, expected_count):
    records = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = [row for row in records if row.get("run_id") == run_id]
    records, duplicates = deduplicate_records(records)
    counts = Counter(row["condition"] for row in records)
    expected_per_condition = expected_count // len(CONDITIONS)
    if duplicates or len(records) != expected_count or any(counts[name] != expected_per_condition for name in CONDITIONS):
        raise ValueError(
            f"{run_id}: expected {expected_count} unique rows and {expected_per_condition} per condition; "
            f"got {len(records)}, duplicates={duplicates}, counts={dict(counts)}"
        )
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--test-run-id", default="alfworld-v7-targeted-test-10x3")
    parser.add_argument("--dev-run-id", default="alfworld-v7-oracle-dev-20x3")
    parser.add_argument("--output-dir", type=Path, default=Path("results/formal_v7"))
    args = parser.parse_args()

    test = load_run(args.results, args.test_run_id, 90)
    dev = load_run(args.results, args.dev_run_id, 180)
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    frozen = output / f"{args.test_run_id}.jsonl"
    ordered = sorted(test, key=lambda row: (row["task_index"], row["repeat"], CONDITIONS.index(row["condition"])))
    frozen.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in ordered), encoding="utf-8")
    digest = hashlib.sha256(frozen.read_bytes()).hexdigest()

    summaries = condition_summary(test)
    dev_summaries = condition_summary(dev)
    families = family_summary(test)
    tasks = task_summary(test)
    paired = [paired_comparison(test, condition) for condition in CONDITIONS if condition != "no_skill"]
    failures = failure_rows(test)
    taxonomy = Counter(row["category"] for row in failures)
    taxonomy_rows = [
        {"category": category, "failures": count, "share": count / len(failures)}
        for category, count in sorted(taxonomy.items())
    ]

    write_csv(output / "condition_summary.csv", summaries)
    write_csv(output / "development_condition_summary.csv", dev_summaries)
    write_csv(output / "family_summary.csv", families)
    write_csv(output / "task_summary.csv", tasks)
    write_csv(output / "paired_comparisons.csv", paired)
    write_csv(output / "failure_taxonomy.csv", taxonomy_rows)
    (output / "failures.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in failures), encoding="utf-8"
    )

    validation = {
        "test_episode_keys": len({(r["task_id"], r["condition"], r["repeat"]) for r in test}),
        "test_tasks": len({r["task_id"] for r in test}),
        "test_condition_counts": dict(Counter(r["condition"] for r in test)),
        "test_family_task_counts": dict(Counter({r["task_id"]: r["task_family"] for r in test}.values())),
        "test_splits": sorted({r["task_id"].split(":")[0] for r in test}),
        "dev_episode_keys": len({(r["task_id"], r["condition"], r["repeat"]) for r in dev}),
        "dev_tasks": len({r["task_id"] for r in dev}),
        "models": sorted({r["model"] for r in test + dev}),
        "temperatures": sorted({r["temperature"] for r in test + dev}),
        "protocols": sorted({r.get("agent_protocol_version") for r in test + dev}),
        "skill_hashes": sorted({r.get("skill_library_sha256") for r in test + dev}),
    }
    manifest = {
        "test_run_id": args.test_run_id, "development_run_id": args.dev_run_id,
        "test_records": len(test), "development_records": len(dev),
        "test_tasks": len({r["task_id"] for r in test}), "development_tasks": len({r["task_id"] for r in dev}),
        "test_conditions": list(CONDITIONS), "repeats": 3,
        "frozen_test_file": str(frozen), "frozen_test_sha256": digest,
        "source_file": str(args.results),
    }
    analysis = {
        "manifest": manifest, "condition_summary": summaries,
        "development_condition_summary": dev_summaries, "family_summary": families,
        "task_summary": tasks, "paired_comparisons": paired,
        "failure_taxonomy": taxonomy_rows, "validation": validation,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "analysis_summary.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(output), "sha256": digest, "test_failures": len(failures), "validation": validation}, ensure_ascii=False))


if __name__ == "__main__":
    main()
