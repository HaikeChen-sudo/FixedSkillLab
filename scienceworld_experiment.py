"""Run frozen No-Skill versus Oracle-Skill ScienceWorld experiments."""

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from scienceworld_agent import CONDITIONS, DEFAULT_CONDITIONS, append_jsonl, environment_limit, run_episode, run_gold_check
from scienceworld_skills import ALL_GOLD_SKILLS
from scienceworld_suites import SCIENCEWORLD_PILOT_6, SUITES, SUITE_VARIATION_SPLITS


PILOT_TASKS = tuple(task for task, _ in SCIENCEWORLD_PILOT_6)


def task_list(value: str) -> List[str]:
    tasks = value.split(",")
    unknown = sorted(set(tasks) - set(ALL_GOLD_SKILLS))
    if unknown:
        raise argparse.ArgumentTypeError(f"tasks without frozen Oracle labels: {', '.join(unknown)}")
    return tasks


def condition_list(value: str) -> List[str]:
    conditions = value.split(",")
    unknown = sorted(set(conditions) - set(CONDITIONS))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown conditions: {', '.join(unknown)}")
    return conditions


def completed_episodes(path: Path, run_id: str, expected=None) -> set:
    if not path.exists():
        return set()
    completed = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("run_id") != run_id:
                continue
            for name, value in (expected or {}).items():
                actual = row.get(name, row.get("max_steps") if name == "environment_max_steps" else None)
                if actual != value:
                    raise ValueError(f"run ID {run_id} has different {name}; use a new run ID")
            completed.add((row["task_name"], row["variation"], row["condition"], row.get("repeat", 0)))
    return completed


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
    parser.add_argument("--max-steps", type=int, default=50, help="Agent trace/action limit; also default environment limit")
    parser.add_argument("--environment-max-steps", type=int, help="independent environment move limit; defaults to --max-steps")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--results", type=Path, default=Path("results/scienceworld_results.jsonl"))
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--order-seed", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--gold-check", action="store_true", help="validate every selected case with local gold paths; no API")
    parser.add_argument("--check-results", type=Path, help="save --gold-check records as JSONL")
    args = parser.parse_args()
    if (args.variation is not None and args.variation < 0) or args.max_steps < 1 or args.repeats < 1:
        parser.error("--variation must be non-negative; --max-steps and --repeats must be positive")
    try:
        cases = experiment_cases(args.suite, args.tasks, args.variation)
        limit = environment_limit(args.max_steps, args.environment_max_steps)
    except ValueError as error:
        parser.error(str(error))
    if args.check_results and not args.gold_check:
        parser.error("--check-results requires --gold-check")
    if args.gold_check:
        success = True
        records = []
        for task_name, variation in cases:
            record = run_gold_check(task_name, variation, args.simplification, args.max_steps, environment_max_steps=limit)
            records.append(record)
            success = success and record["success"]
            print(json.dumps({key: record[key] for key in (
                "task_id", "success", "score", "steps", "environment_moves",
            )}, ensure_ascii=False))
        if args.check_results:
            args.check_results.parent.mkdir(parents=True, exist_ok=True)
            args.check_results.write_text(
                "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in records),
                encoding="utf-8",
            )
        return 0 if success else 1
    if not args.model:
        parser.error("--model is required unless --gold-check is used")

    try:
        completed = completed_episodes(args.results, args.run_id, {
            "model": args.model, "temperature": args.temperature,
            "simplification": args.simplification, "max_steps": args.max_steps,
            "environment_max_steps": limit,
        })
    except ValueError as error:
        parser.error(str(error))
    if completed and not args.resume:
        parser.error("run ID already has results; use --resume or a new run ID")
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
                    args.simplification, args.max_steps, condition, environment_max_steps=limit,
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
