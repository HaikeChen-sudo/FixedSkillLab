"""Print the seven first-pass metrics grouped by experiment condition."""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

from result_utils import deduplicate_records


def episode_metrics(rows):
    successes = sum(row["success"] for row in rows)
    total_tokens = sum(row["total_tokens"] for row in rows)
    average_tokens = total_tokens / len(rows)
    costs = [row["cost_usd"] for row in rows]
    metrics = {
        "task_success_rate": successes / len(rows),
        "average_input_tokens": sum(row["input_tokens"] for row in rows) / len(rows),
        "average_output_tokens": sum(row["output_tokens"] for row in rows) / len(rows),
        "average_total_tokens": average_tokens,
        "average_latency_ms": sum(row["latency_ms"] for row in rows) / len(rows),
        "cost_per_successful_task_usd": sum(costs) / successes if successes and all(cost is not None for cost in costs) else None,
        "average_tool_calls": sum(row["tool_calls"] for row in rows) / len(rows),
        "efficiency_per_1k_tokens": 1000 * (successes / len(rows)) / average_tokens if average_tokens else None,
    }
    if all("score" in row for row in rows):
        metrics["average_score"] = sum(row["score"] for row in rows) / len(rows)
    if all("environment_moves" in row for row in rows):
        metrics["average_environment_moves"] = sum(row["environment_moves"] for row in rows) / len(rows)
    return metrics


def summarize_by_repeat(records):
    """Aggregate each repeat first so standard deviations describe runs, not episodes."""
    grouped = defaultdict(lambda: defaultdict(list))
    for row in records:
        grouped[row["condition"]][row.get("repeat", 0)].append(row)
    result = []
    for condition in sorted(grouped):
        per_repeat = [episode_metrics(rows) for _, rows in sorted(grouped[condition].items())]
        summary = {
            "condition": condition,
            "repeats": len(per_repeat),
            "episodes_per_repeat": [len(rows) for _, rows in sorted(grouped[condition].items())],
        }
        for metric in per_repeat[0]:
            values = [row[metric] for row in per_repeat]
            summary[metric] = None if any(value is None for value in values) else {
                "mean": mean(values),
                "std": stdev(values) if len(values) > 1 else 0.0,
            }
        result.append(summary)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Mini Lab results.jsonl")
    parser.add_argument("results", type=Path)
    parser.add_argument("--run-id", help="only summarize one frozen experiment run")
    parser.add_argument("--deduplicate", action="store_true", help="keep the first saved episode for each task, condition, and repeat")
    parser.add_argument("--repeat-stats", action="store_true", help="report mean and sample standard deviation across repeats")
    args = parser.parse_args()
    records = []
    with args.results.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                if not args.run_id or row["run_id"] == args.run_id:
                    records.append(row)
    duplicates_removed = 0
    if args.deduplicate:
        records, duplicates_removed = deduplicate_records(records)
        print(json.dumps({
            "run_id": args.run_id,
            "records_loaded": len(records) + duplicates_removed,
            "records_kept": len(records),
            "duplicates_removed": duplicates_removed,
        }, ensure_ascii=False))
    groups = defaultdict(list)
    for row in records:
        groups[row["condition"]].append(row)
    for condition in sorted(groups):
        rows = groups[condition]
        print(json.dumps({"condition": condition, "episodes": len(rows), **episode_metrics(rows)}, ensure_ascii=False))
    if args.repeat_stats:
        for summary in summarize_by_repeat(records):
            print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
