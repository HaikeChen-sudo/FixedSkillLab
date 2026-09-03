"""Show task-level failures for Flat Retrieval and Oracle Skill."""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List

from result_utils import deduplicate_records


DEFAULT_CONDITIONS = ("flat_retrieval", "oracle_skill")


def failure_rows(records: Iterable[Dict], conditions: Iterable[str]) -> List[Dict]:
    grouped = defaultdict(list)
    selected = set(conditions)
    for record in records:
        if record["condition"] in selected:
            grouped[(record["condition"], record["task_id"])].append(record)
    rows = []
    for (condition, task_id), episodes in sorted(grouped.items()):
        failures = [episode for episode in episodes if not episode["success"]]
        if not failures:
            continue
        rows.append({
            "condition": condition,
            "task_id": task_id,
            "episodes": len(episodes),
            "successes": len(episodes) - len(failures),
            "failures": len(failures),
            "skills_loaded": episodes[0]["skills_loaded"],
            "gold_skills": episodes[0]["gold_skills"],
            "retrieval_rank": episodes[0]["retrieval_rank"],
            "gold_skill_ranks": episodes[0]["gold_skill_ranks"],
            "failed_repeats": [{
                "repeat": episode["repeat"],
                "final_text": episode["final_text"],
                "trace": episode["trace"],
            } for episode in failures],
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Print failures by task for Flat Retrieval and Oracle Skill")
    parser.add_argument("results", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--conditions", default=",".join(DEFAULT_CONDITIONS))
    parser.add_argument("--deduplicate", action="store_true", help="keep the first saved episode for each task, condition, and repeat")
    args = parser.parse_args()
    conditions = args.conditions.split(",")
    with args.results.open(encoding="utf-8") as handle:
        records = []
        for line in handle:
            if line.strip():
                record = json.loads(line)
                if record["run_id"] == args.run_id:
                    records.append(record)
    if not records:
        print(json.dumps({"run_id": args.run_id, "status": "run_id_not_found"}, ensure_ascii=False))
        return 2
    duplicates_removed = 0
    if args.deduplicate:
        records, duplicates_removed = deduplicate_records(records)
    rows = failure_rows(records, conditions)
    episodes = sum(record["condition"] in conditions for record in records)
    print(json.dumps({
        "run_id": args.run_id,
        "episodes": episodes,
        "duplicates_removed": duplicates_removed,
        "failed_task_conditions": len(rows),
        "message": "No failures found." if not rows else "Failure details follow.",
    }, ensure_ascii=False))
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
