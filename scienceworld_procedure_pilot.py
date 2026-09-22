"""Frozen two-task Procedure-only dev pilot using the existing ScienceWorld Agent."""

import argparse
from dataclasses import fields, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
from unittest.mock import patch

from scienceworld_agent import append_jsonl, run_episode
from scienceworld_procedure_audit import INCLINE_P1_STEP, procedure_arms
from scienceworld_skills import V4B_SKILL_OVERRIDES, loaded_skill_text, versioned_skills


CASES = (("chemistry-mix", 16), ("inclined-plane-determine-angle", 84))
ARMS = ("procedure_p0", "procedure_p1")
MODEL = "deepseek-v4-flash"
TEMPERATURE = 0.0
MAX_STEPS = 100
REPEATS = 1
ORDER_SEED = 20260922
MAX_RECORDED_COST_USD = 0.05
SUITE = "scienceworld-procedure-dev-2"


def arm_skill(task_name, arm):
    if task_name not in {name for name, _ in CASES} or arm not in ARMS:
        raise ValueError(f"unregistered Procedure arm: {task_name}/{arm}")
    v4 = {item.name: item for item in versioned_skills("v4")}
    v4b = {item.name: item for item in versioned_skills("v4b")}
    if task_name == "chemistry-mix":
        name = "chemistry-recipe-mix"
        return v4[name] if arm == "procedure_p0" else v4b[name]
    name = "measure-inclined-plane-angle"
    base = v4b[name]
    return base if arm == "procedure_p0" else replace(
        base, procedure=base.procedure[:2] + (INCLINE_P1_STEP,) + base.procedure[3:],
    )


def plan():
    procedure_arms()  # Reject any unrelated v4-to-v4b edit before using either arm.
    rows = []
    for task_name, variation in CASES:
        p0, p1 = (arm_skill(task_name, arm) for arm in ARMS)
        changed = [field.name for field in fields(p0) if getattr(p0, field.name) != getattr(p1, field.name)]
        if changed != ["procedure"]:
            raise ValueError(f"{task_name} arms changed fields: {changed}")
        for repeat in range(REPEATS):
            order = list(ARMS)
            random.Random(f"{ORDER_SEED}:{task_name}:{variation}:{repeat}").shuffle(order)
            for arm in order:
                item = arm_skill(task_name, arm)
                with patch.dict(V4B_SKILL_OVERRIDES, {item.name: item}):
                    prompt = loaded_skill_text([item.name], "v4b")
                rows.append({
                    "task_name": task_name,
                    "variation": variation,
                    "repeat": repeat,
                    "condition": arm,
                    "skill_name": item.name,
                    "skill_prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                })
    return rows


def run_arm(row):
    item = arm_skill(row["task_name"], row["condition"])
    # The override lives only for this sequential episode; Agent and controller stay unchanged.
    with patch.dict(V4B_SKILL_OVERRIDES, {item.name: item}):
        record = run_episode(
            MODEL, TEMPERATURE, row["task_name"], row["variation"],
            "easy", MAX_STEPS, "oracle_v4",
        )
    if record["skill_prompt_sha256"] != row["skill_prompt_sha256"]:
        raise RuntimeError("Agent loaded a Skill prompt different from the frozen arm")
    if record["agent_protocol_version"] != "scienceworld-v14b" or record["shared_controller_version"] != "shared-state-checkpoint-v1":
        raise RuntimeError("Agent protocol or controller changed during the paired pilot")
    record["condition"] = row["condition"]
    record["procedure_arm"] = row["condition"]
    return record


def existing_records(path, run_id, expected):
    if not path.exists():
        return {}
    rows = {}
    with path.open(encoding="utf-8") as source:
        for line in source:
            record = json.loads(line)
            if record.get("run_id") != run_id:
                continue
            key = (record.get("task_name"), record.get("variation"), record.get("repeat"), record.get("condition"))
            if key not in expected or key in rows:
                raise ValueError(f"unexpected or duplicate episode in run {run_id}: {key}")
            frozen = expected[key]
            if any((
                record.get("model") != MODEL,
                record.get("temperature") != TEMPERATURE,
                record.get("max_steps") != MAX_STEPS,
                record.get("suite") != SUITE,
                record.get("order_seed") != ORDER_SEED,
                record.get("skill_prompt_sha256") != frozen["skill_prompt_sha256"],
            )):
                raise ValueError(f"incompatible resume record in run {run_id}: {key}")
            rows[key] = record
    return rows


def main():
    parser = argparse.ArgumentParser(description="Preview or run the frozen Procedure dev pilot")
    parser.add_argument("--execute", action="store_true", help="call DeepSeek; omitted means no API call")
    parser.add_argument("--run-id", help="required with --execute")
    parser.add_argument("--results", type=Path, default=Path("results/scienceworld_results.jsonl"))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.execute and not args.run_id:
        parser.error("--execute requires --run-id")
    if args.resume and not args.execute:
        parser.error("--resume requires --execute")

    rows = plan()
    if not args.execute:
        print(json.dumps({
            "status": "preview_only", "api_calls": 0, "suite": SUITE,
            "model": MODEL, "temperature": TEMPERATURE, "max_steps": MAX_STEPS,
            "repeats": REPEATS, "order_seed": ORDER_SEED,
            "max_recorded_cost_usd": MAX_RECORDED_COST_USD,
            "warning": "The cost stop is checked between episodes; one episode can cross the threshold.",
            "episodes": rows,
        }, ensure_ascii=False, indent=2))
        return 0

    expected = {(row["task_name"], row["variation"], row["repeat"], row["condition"]): row for row in rows}
    completed = existing_records(args.results, args.run_id, expected)
    if completed and not args.resume:
        parser.error("run-id already has records; use --resume or choose a fresh run-id")
    spent = sum(record["cost_usd"] for record in completed.values())
    for row in rows:
        key = (row["task_name"], row["variation"], row["repeat"], row["condition"])
        if key in completed:
            continue
        if spent >= MAX_RECORDED_COST_USD:
            print(json.dumps({"status": "recorded_cost_stop", "run_id": args.run_id, "spent_usd": spent}, ensure_ascii=False))
            return 2
        record = run_arm(row)
        record.update({
            "schema_version": 1, "run_id": args.run_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "repeat": row["repeat"], "thinking": "disabled", "suite": SUITE,
            "variation_split": "dev", "order_seed": ORDER_SEED,
            "max_recorded_cost_usd": MAX_RECORDED_COST_USD,
        })
        append_jsonl(args.results, record)
        if record["cost_usd"] is None:
            raise RuntimeError("model cost is unavailable; stopping after the recorded episode")
        spent += record["cost_usd"]
        print(json.dumps({
            "run_id": args.run_id, "task_id": record["task_id"],
            "condition": row["condition"], "score": record["score"],
            "success": record["success"], "spent_usd": spent,
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
