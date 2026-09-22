"""Frozen, opt-in Procedure-only holdout; preview never calls DeepSeek."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import scienceworld_procedure_pilot as pilot
from scienceworld_agent import append_jsonl, make_env


ROOT = Path(__file__).resolve().parent
CASES = (
    ("chemistry-mix", 27), ("chemistry-mix", 28), ("chemistry-mix", 29),
    ("inclined-plane-determine-angle", 129),
    ("inclined-plane-determine-angle", 130),
    ("inclined-plane-determine-angle", 131),
)
SUITE = "scienceworld-procedure-holdout-6"
REPEATS = 3
ORDER_SEED = 20260922
MAX_STEPS = 100
MAX_RECORDED_COST_USD = 0.10
MANIFEST = ROOT / "results/scienceworld_procedure_holdout_manifest.json"
PINNED_FILES = (
    "scienceworld_agent.py", "scienceworld_skills.py",
    "scienceworld_procedure_audit.py", "scienceworld_procedure_pilot.py",
    "scienceworld_incline_process_audit.py", "scienceworld_procedure_holdout.py",
)


def frozen_settings():
    return {
        "suite": SUITE, "cases": [{"task_name": name, "variation": variation} for name, variation in CASES],
        "conditions": list(pilot.ARMS), "model": pilot.MODEL,
        "temperature": pilot.TEMPERATURE, "simplification": "easy",
        "max_steps": MAX_STEPS, "repeats": REPEATS, "order_seed": ORDER_SEED,
        "max_recorded_cost_usd": MAX_RECORDED_COST_USD,
    }


def verify_manifest(path=MANIFEST):
    manifest_bytes = path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest["settings"] != frozen_settings():
        raise ValueError("holdout settings differ from the frozen manifest")
    for name in PINNED_FILES:
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        if manifest["sha256"].get(name) != actual:
            raise ValueError(f"frozen file changed: {name}")
    return hashlib.sha256(manifest_bytes).hexdigest()


def verify_test_split():
    # A split mismatch must stop the run before the first paid model call.
    env = make_env(1)
    try:
        for task_name in sorted({name for name, _ in CASES}):
            env.load(task_name, variationIdx=0, simplificationStr="easy")
            official = set(env.get_variations_test())
            requested = {variation for name, variation in CASES if name == task_name}
            if not requested <= official:
                raise ValueError(f"not in official test split: {task_name} {sorted(requested - official)}")
    finally:
        env.close()


def main():
    parser = argparse.ArgumentParser(description="Preview or execute frozen Procedure-only holdout")
    parser.add_argument("--execute", action="store_true", help="call DeepSeek; omitted means no API call")
    parser.add_argument("--run-id", help="required with --execute")
    parser.add_argument("--results", type=Path, default=ROOT / "results/scienceworld_results.jsonl")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.execute and not args.run_id:
        parser.error("--execute requires --run-id")
    if args.resume and not args.execute:
        parser.error("--resume requires --execute")

    manifest_hash = verify_manifest()
    with patch.multiple(
        pilot, CASES=CASES, SUITE=SUITE, REPEATS=REPEATS,
        ORDER_SEED=ORDER_SEED, MAX_STEPS=MAX_STEPS,
        MAX_RECORDED_COST_USD=MAX_RECORDED_COST_USD,
    ):
        rows = pilot.plan()
        if not args.execute:
            print(json.dumps({
                "status": "preview_only", "api_calls": 0, "settings": frozen_settings(),
                "manifest_sha256": manifest_hash, "episodes": rows,
                "warning": "Split is checked against ScienceWorld only when --execute is supplied. The cost stop is checked between episodes.",
            }, ensure_ascii=False, indent=2))
            return 0

        expected = {(row["task_name"], row["variation"], row["repeat"], row["condition"]): row for row in rows}
        completed = pilot.existing_records(args.results, args.run_id, expected)
        if completed and not args.resume:
            parser.error("run-id already has records; use --resume or choose a fresh run-id")
        for key, record in completed.items():
            if record.get("manifest_sha256") != manifest_hash or record.get("variation_split") != "test":
                raise ValueError(f"incompatible holdout record: {key}")
        verify_test_split()
        spent = sum(record["cost_usd"] for record in completed.values())
        for row in rows:
            key = (row["task_name"], row["variation"], row["repeat"], row["condition"])
            if key in completed:
                continue
            if spent >= MAX_RECORDED_COST_USD:
                print(json.dumps({"status": "recorded_cost_stop", "run_id": args.run_id, "spent_usd": spent}))
                return 2
            record = pilot.run_arm(row)
            record.update({
                "schema_version": 1, "run_id": args.run_id,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "repeat": row["repeat"], "thinking": "disabled", "suite": SUITE,
                "variation_split": "test", "order_seed": ORDER_SEED,
                "max_recorded_cost_usd": MAX_RECORDED_COST_USD,
                "manifest_sha256": manifest_hash,
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
