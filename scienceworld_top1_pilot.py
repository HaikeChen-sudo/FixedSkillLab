"""Frozen 36-episode Top-1 development diagnostic; paid calls require --execute."""

import argparse
import json
import math
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from scienceworld_agent import append_jsonl, make_env, run_episode, skill_selection
from scienceworld_hash_audit import digest
from scienceworld_retrieval_baselines import file_hash
from scienceworld_skills import library_hash, loaded_skill_text
from scienceworld_top1_audit import write_new

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "results/scienceworld_top1_new_dev_12"
MANIFEST = ROOT / "results/scienceworld_top1_pilot_manifest.json"
RESULTS = ROOT / "results/scienceworld_top1_pilot.jsonl"
RUN_ID = "scienceworld-top1-mechanism-dev-4x3"
CASES = tuple((task, variation) for task in ("find-living-thing", "find-non-living-thing") for variation in (150, 151))
CONDITIONS = ("no_skill", "semantic_flat_top1", "semantic_body_top1")
MODEL = "deepseek-v4-flash"
LIMIT = 100
REPEATS = 3
ORDER_SEED = 20261008
COST_STOP_USD = 0.25


def plan():
    rows = []
    for repeat in range(REPEATS):
        cases = list(CASES)
        random.Random(f"{ORDER_SEED}:tasks:{repeat}").shuffle(cases)
        for task, variation in cases:
            order = list(CONDITIONS)
            random.Random(f"{ORDER_SEED}:{task}:{variation}").shuffle(order)
            order = order[repeat:] + order[:repeat]
            for position, condition in enumerate(order):
                rows.append(dict(task_name=task, variation=variation, condition=condition, repeat=repeat,
                                 order_position=position, plan_index=len(rows)))
    return rows


def current_manifest():
    audit = json.loads((SOURCE / "audit.json").read_text())
    verification = json.loads((SOURCE / "verification.json").read_text())
    source_manifest = json.loads((SOURCE / "manifest.json").read_text())
    if (audit["manifest_sha256"] != file_hash(SOURCE / "manifest.json")
            or audit["query_file_sha256"] != file_hash(SOURCE / "queries.json")
            or verification["audit_sha256"] != file_hash(SOURCE / "audit.json")):
        raise ValueError("Offline audit provenance mismatch")
    cases = {r["task_id"]: r for r in audit["cases"] if (r["task_name"], r["variation"]) in CASES}
    if len(cases) != len(CASES) or source_manifest["library_sha256"] != library_hash("v3"):
        raise ValueError("Missing pilot cases or changed Skill library")
    files = ("agent.py", "scienceworld_agent.py", "scienceworld_top1_pilot.py", "scienceworld_skills.py",
             "scienceworld_strong_retrieval.py", "scienceworld_retrieval.py", "scienceworld_retrieval_baselines.py",
             "scienceworld_hash_audit.py", "scienceworld_top1_audit.py",
             "results/scienceworld_retrieval_baselines_2026-09-24/summary.json")
    runtime = json.loads((ROOT / "results/scienceworld_strong_confirmation_manifest.json").read_text())["scienceworld_runtime"]
    if any(runtime[k] != source_manifest["runtime"][k] for k in ("package_version", "jar_sha256")):
        raise ValueError("Offline and online environment versions differ")
    return dict(run_id=RUN_ID, study_type="targeted_development_diagnostic_not_heldout",
                episode_plan=plan(), model=MODEL, temperature=0.0, thinking="disabled", simplification="easy",
                agent_max_steps=LIMIT, environment_max_steps=LIMIT, order_seed=ORDER_SEED,
                cost_stop_usd=COST_STOP_USD, scienceworld_runtime=runtime,
                library_sha256=library_hash("v3"), cases=cases,
                source_sha256={name: file_hash(SOURCE / name) for name in ("manifest.json", "queries.json", "audit.json", "verification.json")},
                file_sha256={name: file_hash(ROOT / name) for name in files})


def validate_record(record, expected, manifest, manifest_sha):
    fixed = dict(expected, run_id=RUN_ID, top1_manifest_sha256=manifest_sha, model=MODEL, temperature=0.0,
                 thinking="disabled", simplification="easy", max_steps=LIMIT, agent_max_steps=LIMIT,
                 environment_max_steps=LIMIT, variation_split="dev", budget_protocol_version="split-budgets-v1",
                 agent_protocol_version="scienceworld-v2", environment="scienceworld")
    if any(record.get(k) != v for k, v in fixed.items()):
        raise ValueError("Saved episode differs from the frozen Top-1 protocol")
    task_id = f"{expected['task_name']}:v{expected['variation']:03d}"
    case = manifest["cases"][task_id]
    if record.get("task_id") != task_id or record.get("retrieval_query") != case["query"]:
        raise ValueError("Task identity or task query changed")
    if not isinstance(record.get("success"), bool) or record["success"] != (record.get("score", -1) >= 100):
        raise ValueError("Success must match the environment score")
    for key in ("input_tokens", "output_tokens", "total_tokens", "latency_ms", "routing_ms", "runner_ms", "cost_usd", "llm_calls", "tool_calls"):
        value = record.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("Invalid accounting: " + key)
    if record["total_tokens"] != record["input_tokens"] + record["output_tokens"]:
        raise ValueError("Token totals do not reconcile")
    if record.get("controller_interventions") != 0 or record.get("shared_controller_version") is not None:
        raise ValueError("Unexpected execution controller")
    if expected["condition"] == "no_skill":
        if record.get("skills_loaded") != [] or any(record.get(k) is not None for k in ("skill_prompt_sha256", "skill_library_version", "retrieval_metadata")):
            raise ValueError("No Skill contains Skill guidance")
        return
    mode = "flat" if expected["condition"] == "semantic_flat_top1" else "body"
    name = case["top1"][mode]
    metadata = record.get("retrieval_metadata") or {}
    hits = record.get("retrieval") or []
    if (record.get("skills_loaded") != [name] or len(hits) != 1 or hits[0].get("name") != name
            or hits[0].get("rank") != 1 or record.get("skill_library_version") != "v3"
            or record.get("skill_library_sha256") != manifest["library_sha256"]
            or record.get("skill_render_mode") != "full"
            or record.get("skill_prompt_sha256") != case["prompt_sha256"][mode]["1"]
            or record.get("gold_skill_ranks") != [1 if name == case["gold_skill"] else None]
            or metadata.get("top_k") != 1 or metadata.get("index_mode") != mode
            or metadata.get("query_sha256") != case["query_sha256"]
            or metadata.get("selection_version") != "semantic-top1-v1"
            or metadata.get("truncated") is not False):
        raise ValueError("Loaded Top-1 Skill differs from frozen offline selection")


def saved_records(path, manifest, manifest_sha):
    records = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            index = record.get("plan_index")
            if type(index) is not int or not 0 <= index < len(manifest["episode_plan"]) or index in records:
                raise ValueError("Unexpected or duplicate episode; refusing resume")
            validate_record(record, manifest["episode_plan"][index], manifest, manifest_sha)
            records[index] = record
    return records


def preflight(manifest):
    from importlib.metadata import version
    from scienceworld.constants import JAR_PATH
    import scienceworld.scienceworld as wrapper

    runtime = dict(package_version=version("scienceworld"), jar_sha256=file_hash(Path(JAR_PATH)),
                   wrapper_sha256=file_hash(Path(wrapper.__file__)))
    if runtime != manifest["scienceworld_runtime"]:
        raise ValueError("ScienceWorld runtime changed")
    env = make_env(LIMIT)
    try:
        for task, variation in CASES:
            case = manifest["cases"][f"{task}:v{variation:03d}"]
            env.load(task, variationIdx=variation, simplificationStr="easy")
            if variation not in env.get_variations_dev():
                raise ValueError("Pilot case is outside official dev split")
            _, info = env.reset()
            if info["taskDesc"] != case["query"]:
                raise ValueError("Environment query differs from offline audit")
            for condition, mode in (("semantic_flat_top1", "flat"), ("semantic_body_top1", "body")):
                selection = skill_selection(condition, task, case["query"])
                if (selection.names != [case["top1"][mode]]
                        or digest(loaded_skill_text(selection.names, "v3").encode()) != case["prompt_sha256"][mode]["1"]):
                    raise ValueError("Online Top-1 differs from frozen offline audit")
    finally:
        env.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    for name in ("prepare", "check", "status", "execute"):
        action.add_argument("--" + name, action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    if args.resume and not args.execute:
        parser.error("--resume requires --execute")
    manifest = current_manifest()
    if not any((args.prepare, args.check, args.status, args.execute)):
        print(json.dumps(dict(status="preview_only", planned=len(plan()), api_calls=0, run_id=RUN_ID)))
        return 0
    if args.prepare and not MANIFEST.exists():
        write_new(MANIFEST, manifest)
    if not MANIFEST.exists() or json.loads(MANIFEST.read_text()) != manifest:
        parser.error("Frozen manifest missing or changed; prepare once, never overwrite an existing manifest")
    manifest_sha = file_hash(MANIFEST)
    saved = saved_records(RESULTS, manifest, manifest_sha)
    spent = sum(r["cost_usd"] for r in saved.values())
    print(json.dumps(dict(completed=len(saved), planned=len(plan()), spent_usd=spent, run_id=RUN_ID)), flush=True)
    if args.prepare or args.status:
        return 0
    if args.check:
        preflight(manifest)
        print(json.dumps(dict(status="local_checks_passed", api_calls=0)), flush=True)
        return 0
    if len(saved) == len(plan()):
        return 0
    if saved and not args.resume:
        parser.error("Use --execute --resume to skip completed episodes")
    if not os.environ.get("DEEPSEEK_API_KEY"):
        parser.error("Set DEEPSEEK_API_KEY in this terminal; do not paste it into chat")
    if spent >= COST_STOP_USD:
        parser.error("Recorded cost stop reached; no further API calls")
    preflight(manifest)
    for expected in manifest["episode_plan"]:
        if expected["plan_index"] in saved:
            continue
        if spent >= COST_STOP_USD:
            print(json.dumps(dict(status="recorded_cost_stop", spent_usd=spent)), flush=True)
            return 2
        started = time.perf_counter()
        record = run_episode(MODEL, 0.0, expected["task_name"], expected["variation"], "easy", LIMIT,
                             expected["condition"], environment_max_steps=LIMIT)
        record.update(expected, run_id=RUN_ID, schema_version=1, thinking="disabled", variation_split="dev",
                      suite="scienceworld-top1-mechanism-dev-4", top1_manifest_sha256=manifest_sha,
                      timestamp_utc=datetime.now(timezone.utc).isoformat(),
                      runner_ms=round((time.perf_counter() - started) * 1000))
        # Preserve a completed paid outcome even if a post-run protocol check fails.
        append_jsonl(RESULTS, record)
        validate_record(record, expected, manifest, manifest_sha)
        saved[expected["plan_index"]] = record
        spent += record["cost_usd"]
        print(json.dumps(dict(completed=len(saved), planned=len(plan()), task_id=record["task_id"],
                              condition=record["condition"], repeat=record["repeat"], success=record["success"],
                              score=record["score"], spent_usd=spent)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
