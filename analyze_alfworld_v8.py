"""Freeze and analyze the task-disjoint v8 ALFWorld confirmation run."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

from analyze_alfworld_v7 import (
    CONDITIONS,
    LABELS,
    condition_summary,
    family_summary,
    paired_comparison,
    task_summary,
    write_csv,
)
from result_utils import deduplicate_records


EXPECTED_TASKS = {
    "valid_seen:010", "valid_seen:013", "valid_seen:047", "valid_seen:058",
    "valid_seen:059", "valid_seen:070", "valid_seen:078", "valid_seen:080",
    "valid_seen:087", "valid_seen:089", "valid_seen:092", "valid_seen:104",
    "valid_seen:120", "valid_seen:121", "valid_seen:123", "valid_seen:125",
    "valid_seen:128", "valid_seen:135", "valid_seen:136", "valid_seen:139",
}
METRICS = (
    "input_tokens", "output_tokens", "total_tokens", "latency_ms",
    "cost_usd", "tool_calls",
)


def load_run(source, run_id):
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [row for row in rows if row.get("run_id") == run_id]
    rows, duplicates = deduplicate_records(rows)
    counts = Counter(row["condition"] for row in rows)
    tasks = {row["task_id"] for row in rows}
    keys = {(row["task_id"], row["condition"], row["repeat"]) for row in rows}
    if duplicates or len(rows) != 180 or len(keys) != 180:
        raise ValueError(f"expected 180 unique episodes; got rows={len(rows)}, keys={len(keys)}, duplicates={duplicates}")
    if counts != Counter({name: 60 for name in CONDITIONS}):
        raise ValueError(f"unexpected condition counts: {dict(counts)}")
    if tasks != EXPECTED_TASKS:
        raise ValueError(f"unexpected task set: missing={sorted(EXPECTED_TASKS-tasks)}, extra={sorted(tasks-EXPECTED_TASKS)}")
    expected = {
        "model": {"deepseek-v4-flash"}, "temperature": {0.0},
        "agent_protocol_version": {"v7-versioned-oracle"},
        "suite": {"alfworld-v8-confirm-20"}, "split": {"valid_seen"},
    }
    for field, values in expected.items():
        actual = {row.get(field) for row in rows}
        if actual != values:
            raise ValueError(f"{field}: expected {values}, got {actual}")
    return rows


def failure_rows(rows):
    return [
        {
            "condition": row["condition"], "task_id": row["task_id"],
            "task_family": row["task_family"], "repeat": row["repeat"],
            "category": "step_budget_exhausted" if row["steps"] >= 100 else "execution_error_other",
            "steps": row["steps"], "total_tokens": row["total_tokens"],
            "goal": row.get("retrieval_query", ""),
            "last_actions": [step.get("command", "") for step in row.get("trace", [])][-8:],
        }
        for row in rows if not row["success"]
    ]


def paired_directions(rows, condition, baseline="no_skill"):
    by_key = {(row["task_id"], row["repeat"], row["condition"]): row for row in rows}
    output = []
    for family in ("all", "heat_then_place", "two_object_place"):
        task_ids = sorted({row["task_id"] for row in rows if family == "all" or row["task_family"] == family})
        for metric in METRICS:
            differences = []
            for task_id in task_ids:
                for repeat in range(3):
                    differences.append(
                        by_key[(task_id, repeat, condition)][metric]
                        - by_key[(task_id, repeat, baseline)][metric]
                    )
            output.append({
                "condition": condition, "label": LABELS[condition], "baseline": baseline,
                "task_family": family, "metric": metric, "episodes": len(differences),
                "mean_difference": mean(differences), "median_difference": median(differences),
                "lower": sum(value < 0 for value in differences),
                "equal": sum(value == 0 for value in differences),
                "higher": sum(value > 0 for value in differences),
            })
    return output


def task_differences(rows, condition="oracle_v7", baseline="no_skill"):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["task_id"], row["task_index"], row["task_family"], row["condition"])].append(row)
    output = []
    for task_id in sorted(EXPECTED_TASKS):
        keys = [key for key in grouped if key[0] == task_id]
        task_index, family = keys[0][1], keys[0][2]
        a, b = grouped[(task_id, task_index, family, condition)], grouped[(task_id, task_index, family, baseline)]
        output.append({
            "task_id": task_id, "task_index": task_index, "task_family": family,
            "condition": condition, "baseline": baseline,
            "success_rate_difference": mean(int(r["success"]) for r in a) - mean(int(r["success"]) for r in b),
            **{f"{metric}_difference": mean(r[metric] for r in a) - mean(r[metric] for r in b) for metric in METRICS},
        })
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--run-id", default="alfworld-v8-confirm-20x3")
    parser.add_argument("--output-dir", type=Path, default=Path("results/formal_v8"))
    args = parser.parse_args()
    rows = load_run(args.results, args.run_id)
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    frozen = output / f"{args.run_id}.jsonl"
    ordered = sorted(rows, key=lambda row: (row["task_index"], row["repeat"], CONDITIONS.index(row["condition"])))
    frozen.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in ordered), encoding="utf-8")
    digest = hashlib.sha256(frozen.read_bytes()).hexdigest()

    summaries = condition_summary(rows)
    families = family_summary(rows)
    tasks = task_summary(rows)
    paired = [paired_comparison(rows, name, iterations=20000, seed=20260908) for name in CONDITIONS if name != "no_skill"]
    directions = [item for name in ("oracle_v5", "oracle_v7") for item in paired_directions(rows, name)]
    differences = task_differences(rows)
    failures = failure_rows(rows)
    taxonomy = Counter(row["category"] for row in failures)
    taxonomy_rows = [{"category": key, "failures": value, "share": value / len(failures)} for key, value in sorted(taxonomy.items())]

    for filename, data in (
        ("condition_summary.csv", summaries), ("family_summary.csv", families),
        ("task_summary.csv", tasks), ("paired_comparisons.csv", paired),
        ("paired_directions.csv", directions), ("task_differences.csv", differences),
        ("failure_taxonomy.csv", taxonomy_rows),
    ):
        write_csv(output / filename, data)
    (output / "failures.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in failures), encoding="utf-8")

    validation = {
        "episode_keys": len({(r["task_id"], r["condition"], r["repeat"]) for r in rows}),
        "tasks": len({r["task_id"] for r in rows}),
        "condition_counts": dict(Counter(r["condition"] for r in rows)),
        "family_task_counts": dict(Counter({r["task_id"]: r["task_family"] for r in rows}.values())),
        "models": sorted({r["model"] for r in rows}),
        "temperatures": sorted({r["temperature"] for r in rows}),
        "protocols": sorted({r["agent_protocol_version"] for r in rows}),
        "suites": sorted({r["suite"] for r in rows}), "splits": sorted({r["split"] for r in rows}),
    }
    manifest = {
        "run_id": args.run_id, "records": len(rows), "tasks": len(EXPECTED_TASKS),
        "conditions": list(CONDITIONS), "repeats": 3, "source_file": str(args.results),
        "frozen_file": str(frozen), "frozen_sha256": digest,
    }
    analysis = {
        "manifest": manifest, "condition_summary": summaries, "family_summary": families,
        "task_summary": tasks, "paired_comparisons": paired, "paired_directions": directions,
        "task_differences": differences, "failure_taxonomy": taxonomy_rows,
        "failures": failures, "validation": validation,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "analysis_summary.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(output), "sha256": digest, "failures": len(failures), "validation": validation}, ensure_ascii=False))


if __name__ == "__main__":
    main()
