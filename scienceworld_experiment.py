"""Run the 6-task No-Skill versus Oracle-Skill ScienceWorld pilot."""

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from scienceworld_agent import CONDITIONS, DEFAULT_CONDITIONS, append_jsonl, run_episode
from scienceworld_skills import GOLD_SKILLS


PILOT_TASKS = tuple(GOLD_SKILLS)


def task_list(value: str) -> List[str]:
    tasks = value.split(",")
    unknown = sorted(set(tasks) - set(GOLD_SKILLS))
    if unknown:
        raise argparse.ArgumentTypeError(f"tasks without frozen Oracle labels: {', '.join(unknown)}")
    return tasks


def condition_list(value: str) -> List[str]:
    conditions = value.split(",")
    unknown = sorted(set(conditions) - set(CONDITIONS))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown conditions: {', '.join(unknown)}")
    return conditions


def completed_episodes(path: Path, run_id: str) -> set:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as handle:
        return {
            (row["task_name"], row["variation"], row["condition"], row.get("repeat", 0))
            for line in handle if line.strip()
            for row in [json.loads(line)]
            if row.get("run_id") == run_id
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the first fixed-Skill ScienceWorld pilot")
    parser.add_argument("--model", required=True)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--tasks", type=task_list, default=list(PILOT_TASKS), help="comma-separated task names")
    parser.add_argument("--conditions", type=condition_list, default=list(DEFAULT_CONDITIONS))
    parser.add_argument("--variation", type=int, default=0)
    parser.add_argument("--simplification", default="easy")
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--results", type=Path, default=Path("results/scienceworld_results.jsonl"))
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--order-seed", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.variation < 0 or args.max_steps < 1 or args.repeats < 1:
        parser.error("--variation must be non-negative; --max-steps and --repeats must be positive")

    completed = completed_episodes(args.results, args.run_id) if args.resume else set()
    for task_name in args.tasks:
        for repeat in range(args.repeats):
            conditions = list(args.conditions)
            random.Random(f"{args.order_seed}:{task_name}:{args.variation}:{repeat}").shuffle(conditions)
            for condition in conditions:
                key = (task_name, args.variation, condition, repeat)
                if key in completed:
                    print(json.dumps({
                        "run_id": args.run_id,
                        "task_id": f"{task_name}:v{args.variation:03d}",
                        "condition": condition,
                        "status": "skipped_existing",
                    }, ensure_ascii=False))
                    continue
                started = time.perf_counter()
                record = run_episode(
                    args.model, args.temperature, task_name, args.variation,
                    args.simplification, args.max_steps, condition,
                )
                record.update({
                    "schema_version": 1,
                    "run_id": args.run_id,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "repeat": repeat,
                    "thinking": "disabled",
                    "suite": "scienceworld-pilot-6",
                })
                append_jsonl(args.results, record)
                print(json.dumps({
                    "run_id": args.run_id,
                    "task_id": record["task_id"],
                    "condition": condition,
                    "score": record["score"],
                    "success": record["success"],
                    "latency_ms": record["latency_ms"],
                    "runner_ms": round((time.perf_counter() - started) * 1000),
                }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
