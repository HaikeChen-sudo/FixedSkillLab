"""Run frozen No-Skill versus Oracle-Skill ScienceWorld experiments."""

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from scienceworld_agent import CONDITIONS, DEFAULT_CONDITIONS, append_jsonl, run_episode, run_gold_check
from scienceworld_skills import GOLD_SKILLS
from scienceworld_suites import SCIENCEWORLD_PILOT_6, SUITES, SUITE_VARIATION_SPLITS


PILOT_TASKS = tuple(task for task, _ in SCIENCEWORLD_PILOT_6)


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


def experiment_cases(suite, tasks, variation):
    if suite and tasks:
        raise ValueError("--suite and --tasks cannot be used together")
    if suite and variation is not None:
        raise ValueError("--variation cannot override a frozen suite")
    if suite:
        return list(SUITES[suite])
    return [(task, variation if variation is not None else 0) for task in (tasks or PILOT_TASKS)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fixed-Skill ScienceWorld experiments")
    parser.add_argument("--model", help="DeepSeek model ID; not needed for --gold-check")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--tasks", type=task_list, help="comma-separated task names")
    parser.add_argument("--suite", choices=sorted(SUITES), help="frozen task-specific variation suite")
    parser.add_argument("--conditions", type=condition_list, default=list(DEFAULT_CONDITIONS))
    parser.add_argument("--variation", type=int, help="one variation for custom --tasks; default: 0")
    parser.add_argument("--simplification", default="easy")
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--results", type=Path, default=Path("results/scienceworld_results.jsonl"))
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--order-seed", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--gold-check", action="store_true", help="validate every selected case with local gold paths; no API")
    args = parser.parse_args()
    if (args.variation is not None and args.variation < 0) or args.max_steps < 1 or args.repeats < 1:
        parser.error("--variation must be non-negative; --max-steps and --repeats must be positive")
    try:
        cases = experiment_cases(args.suite, args.tasks, args.variation)
    except ValueError as error:
        parser.error(str(error))
    if args.gold_check:
        success = True
        for task_name, variation in cases:
            record = run_gold_check(task_name, variation, args.simplification, args.max_steps)
            success = success and record["success"]
            print(json.dumps({key: record[key] for key in (
                "task_id", "success", "score", "steps", "environment_moves",
            )}, ensure_ascii=False))
        return 0 if success else 1
    if not args.model:
        parser.error("--model is required unless --gold-check is used")

    completed = completed_episodes(args.results, args.run_id) if args.resume else set()
    for task_name, variation in cases:
        for repeat in range(args.repeats):
            conditions = list(args.conditions)
            random.Random(f"{args.order_seed}:{task_name}:{variation}:{repeat}").shuffle(conditions)
            for condition in conditions:
                key = (task_name, variation, condition, repeat)
                if key in completed:
                    print(json.dumps({
                        "run_id": args.run_id,
                        "task_id": f"{task_name}:v{variation:03d}",
                        "condition": condition,
                        "status": "skipped_existing",
                    }, ensure_ascii=False))
                    continue
                started = time.perf_counter()
                record = run_episode(
                    args.model, args.temperature, task_name, variation,
                    args.simplification, args.max_steps, condition,
                )
                record.update({
                    "schema_version": 1,
                    "run_id": args.run_id,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "repeat": repeat,
                    "thinking": "disabled",
                    "suite": args.suite or "scienceworld-custom",
                    "variation_split": SUITE_VARIATION_SPLITS.get(args.suite),
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
