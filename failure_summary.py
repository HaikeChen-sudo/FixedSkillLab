"""Print a compact failure summary without dumping complete agent trajectories."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from result_utils import deduplicate_records


def rejected_actions(record):
    return sum(not step.get("result", {}).get("ok", False) for step in record.get("trace", []))


def summarize_failures(records):
    by_condition = defaultdict(list)
    by_task = defaultdict(dict)
    for record in records:
        by_condition[record["condition"]].append(record)
        if not record["success"]:
            by_task[record["task_id"]][record["condition"]] = by_task[record["task_id"]].get(record["condition"], 0) + 1

    conditions = []
    for condition, episodes in sorted(by_condition.items()):
        failed = [record for record in episodes if not record["success"]]
        rejections = [rejected_actions(record) for record in failed]
        conditions.append({
            "condition": condition,
            "episodes": len(episodes),
            "failures": len(failed),
            "failed_task_ids": sorted({record["task_id"] for record in failed}),
            "failed_task_families": dict(sorted(Counter(record.get("task_family") or "unknown" for record in failed).items())),
            "failed_episodes_with_rejected_actions": sum(count > 0 for count in rejections),
            "average_rejected_actions_per_failed_episode": sum(rejections) / len(rejections) if rejections else 0.0,
            "episodes_at_50_tool_calls": sum(record.get("tool_calls") == 50 for record in failed),
        })
    tasks = [
        {"task_id": task_id, "failures_by_condition": failures}
        for task_id, failures in sorted(by_task.items())
    ]
    return conditions, tasks


def main() -> int:
    parser = argparse.ArgumentParser(description="Print concise ALFWorld failure counts")
    parser.add_argument("results", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--deduplicate", action="store_true")
    args = parser.parse_args()
    records = [
        json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("run_id") == args.run_id
    ]
    if not records:
        print(json.dumps({"run_id": args.run_id, "status": "run_id_not_found"}, ensure_ascii=False))
        return 2
    duplicates_removed = 0
    if args.deduplicate:
        records, duplicates_removed = deduplicate_records(records)
    conditions, tasks = summarize_failures(records)
    print(json.dumps({
        "run_id": args.run_id,
        "episodes": len(records),
        "duplicates_removed": duplicates_removed,
        "failed_episodes": sum(not record["success"] for record in records),
    }, ensure_ascii=False))
    for row in conditions:
        print(json.dumps(row, ensure_ascii=False))
    print(json.dumps({"failed_tasks": tasks}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
