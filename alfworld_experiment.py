"""Run the frozen A-E conditions on selected text-only ALFWorld games."""

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from alfworld_agent import CONDITIONS, run_episode
from alfworld_suites import SUITE_FAMILIES, SUITES


def condition_list(value: str) -> List[str]:
    names = value.split(",")
    unknown = sorted(set(names) - set(CONDITIONS))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown conditions: {', '.join(unknown)}")
    return names


def task_list(value: str) -> List[int]:
    try:
        tasks = [int(item) for item in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("--tasks must contain comma-separated integer indexes") from error
    if not tasks or any(item < 0 for item in tasks):
        raise argparse.ArgumentTypeError("--tasks must contain non-negative indexes")
    return tasks


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def completed_episodes(path: Path, run_id: str) -> set:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as handle:
        return {
            (row["task_index"], row["condition"], row["repeat"])
            for line in handle if line.strip()
            for row in [json.loads(line)]
            if row.get("run_id") == run_id
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fixed-Skill A-E ALFWorld experiments")
    parser.add_argument("--model", required=True)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--tasks", type=task_list, help="comma-separated zero-based game indexes; default: 0 through 9")
    parser.add_argument("--suite", choices=sorted(SUITES), help="frozen named task suite; cannot be combined with --tasks")
    parser.add_argument("--conditions", type=condition_list, default=list(CONDITIONS))
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--split", default="valid_unseen", choices=("valid_seen", "valid_unseen"))
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--data-dir", type=Path, default=Path(".alfworld-data"))
    parser.add_argument("--results", type=Path, default=Path("results/alfworld_results.jsonl"))
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--order-seed", type=int, default=0)
    parser.add_argument("--resume", action="store_true", help="skip episodes already saved under this run ID")
    args = parser.parse_args()
    if args.repeats < 1 or args.max_steps < 1:
        parser.error("--repeats and --max-steps must be positive")
    if args.tasks is not None and args.suite:
        parser.error("--tasks and --suite cannot be used together")
    task_indexes = list(SUITES[args.suite]) if args.suite else args.tasks or list(range(10))

    completed = completed_episodes(args.results, args.run_id) if args.resume else set()
    for task_index in task_indexes:
        for repeat in range(args.repeats):
            conditions = list(args.conditions)
            random.Random(f"{args.order_seed}:{task_index}:{repeat}").shuffle(conditions)
            for condition in conditions:
                if (task_index, condition, repeat) in completed:
                    print(json.dumps({"run_id": args.run_id, "task_id": f"{args.split}:{task_index:03d}", "condition": condition, "status": "skipped_existing"}, ensure_ascii=False))
                    continue
                started = time.perf_counter()
                record = run_episode(args.model, args.temperature, args.data_dir, args.split, args.max_steps, task_index, condition)
                record.update({
                    "schema_version": 1,
                    "run_id": args.run_id,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "split": args.split,
                    "repeat": repeat,
                    "thinking": "disabled",
                    "suite": args.suite,
                    "task_family": SUITE_FAMILIES.get(args.suite, {}).get(task_index),
                })
                append_jsonl(args.results, record)
                print(json.dumps({
                    "run_id": args.run_id,
                    "task_id": record["task_id"],
                    "condition": condition,
                    "success": record["success"],
                    "latency_ms": record["latency_ms"],
                    "runner_ms": round((time.perf_counter() - started) * 1000),
                }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
