"""Twelve seen-dev episodes; preview by default, paid execution only with --execute."""

import argparse
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from scienceworld_agent import append_jsonl, make_env, run_episode
from scienceworld_skills import library_hash, loaded_skill_text


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "results/scienceworld_budget_dev_manifest.json"
RESULTS = ROOT / "results/scienceworld_budget_dev.jsonl"
TASK = "inclined-plane-determine-angle"
VARIATIONS = (84, 85, 86)
CONDITIONS = ("no_skill", "semantic_body_retrieval")
MODEL = "deepseek-v4-flash"
AGENT_LIMIT = 100
COST_STOP_USD = 0.25


def plan():
    rows = []
    for index, variation in enumerate(VARIATIONS):
        conditions = CONDITIONS if index % 2 == 0 else CONDITIONS[::-1]
        for condition in conditions:
            # Across six task/condition pairs, each budget runs first three times.
            limits = (100, 200) if (index + CONDITIONS.index(condition)) % 2 == 0 else (200, 100)
            for limit in limits:
                rows.append(dict(task_name=TASK, variation=variation, condition=condition,
                                 repeat=0, environment_max_steps=limit, plan_index=len(rows),
                                 run_id=f"scienceworld-budget-dev-env{limit}-3x1"))
    return rows


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_manifest():
    files = ("agent.py", "scienceworld_agent.py", "scienceworld_skills.py", "scienceworld_retrieval.py",
             "scienceworld_strong_retrieval.py", "scienceworld_retrieval_baselines.py",
             "scienceworld_hash_audit.py", "scienceworld_budget_pilot.py",
             "results/scienceworld_retrieval_baselines_2026-09-24/summary.json")
    return dict(episode_plan=plan(), model=MODEL, temperature=0.0, simplification="easy",
                thinking="disabled", agent_max_steps=AGENT_LIMIT, cost_stop_usd=COST_STOP_USD,
                variation_split="dev", library_sha256=library_hash("v4d"),
                file_sha256={name: file_hash(ROOT / name) for name in files},
                scienceworld_runtime=json.loads((ROOT / "results/scienceworld_strong_confirmation_manifest.json").read_text())["scienceworld_runtime"])


def validate_record(record, expected, manifest_sha):
    fixed = dict(expected, budget_manifest_sha256=manifest_sha, model=MODEL, temperature=0.0,
                 simplification="easy", max_steps=AGENT_LIMIT, agent_max_steps=AGENT_LIMIT,
                 variation_split="dev", budget_protocol_version="split-budgets-v1")
    if any(record.get(key) != value for key, value in fixed.items()):
        raise ValueError("Saved episode differs from the budget protocol; do not reuse this result file")
    if not isinstance(record.get("success"), bool) or record["success"] != (record.get("score", -1) >= 100):
        raise ValueError("Success must match the environment score")
    for key in ("input_tokens", "output_tokens", "total_tokens", "latency_ms", "cost_usd"):
        value = record.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid accounting: {key}")
    if record["total_tokens"] != record["input_tokens"] + record["output_tokens"]:
        raise ValueError("Token accounting mismatch")
    if not isinstance(record.get("retrieval_query"), str) or not record["retrieval_query"].strip():
        raise ValueError("Missing task query")
    names = record.get("skills_loaded")
    if expected["condition"] == "no_skill":
        if names != [] or record.get("skill_prompt_sha256") is not None:
            raise ValueError("No Skill loaded Skill guidance")
    else:
        if not isinstance(names, list) or len(names) != 3 or len(set(names)) != 3:
            raise ValueError("Semantic Body must load three distinct Skills")
        prompt_hash = hashlib.sha256(loaded_skill_text(names, "v4d").encode()).hexdigest()
        if record.get("skill_library_sha256") != library_hash("v4d") or record.get("skill_prompt_sha256") != prompt_hash:
            raise ValueError("Skill contents differ from the fixed library")


def saved_records(path, manifest_sha):
    saved = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            index = record.get("plan_index")
            if type(index) is not int or not 0 <= index < len(plan()) or index in saved:
                raise ValueError("Unexpected or duplicate budget episode")
            validate_record(record, plan()[index], manifest_sha)
            saved[index] = record
    for variation in VARIATIONS:
        for condition in CONDITIONS:
            pair = [r for r in saved.values() if r["variation"] == variation and r["condition"] == condition]
            if len(pair) == 2:
                for field in ("retrieval_query", "skills_loaded", "skill_prompt_sha256", "skill_library_sha256"):
                    if pair[0].get(field) != pair[1].get(field):
                        raise ValueError(f"Budget pair differs in {field}; saved both outcomes, stop for inspection")
    return saved


def preflight(manifest):
    from importlib.metadata import version
    from scienceworld.constants import JAR_PATH
    import scienceworld.scienceworld as wrapper
    from scienceworld_strong_retrieval import strong_retrieve

    actual = dict(package_version=version("scienceworld"), jar_sha256=file_hash(Path(JAR_PATH)),
                  wrapper_sha256=file_hash(Path(wrapper.__file__)))
    if actual != manifest["scienceworld_runtime"]:
        raise ValueError("ScienceWorld runtime changed")
    env = make_env(1)
    try:
        env.load(TASK, variationIdx=0, simplificationStr="easy")
        if not set(VARIATIONS).issubset(env.get_variations_dev()):
            raise ValueError("Pilot cases are not all in the official dev split")
    finally:
        env.close()
    strong_retrieve("Compare inclined plane B and inclined plane F.", True, "v4d", "minilm")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare", action="store_true", help="freeze local code and plan; no API or Java")
    mode.add_argument("--check", action="store_true", help="local runtime/split/encoder check; no API")
    mode.add_argument("--execute", action="store_true", help="enable paid DeepSeek episodes")
    mode.add_argument("--status", action="store_true", help="inspect saved progress without API or Java")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--results", type=Path, default=RESULTS)
    args = parser.parse_args(argv)
    if args.resume and not args.execute:
        parser.error("--resume requires --execute")
    manifest = current_manifest()
    if args.prepare:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        if not MANIFEST.exists():
            with MANIFEST.open("x", encoding="utf-8") as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
    if not any((args.prepare, args.check, args.execute, args.status)):
        print(json.dumps(dict(status="preview_only", api_calls=0, episodes=12, plan=plan()), indent=2))
        return 0
    if not MANIFEST.exists() or json.loads(MANIFEST.read_text()) != manifest:
        parser.error("Missing or changed frozen manifest; use --prepare before the first run, never overwrite a used manifest")
    manifest_sha = file_hash(MANIFEST)
    saved = saved_records(args.results, manifest_sha)
    print(json.dumps(dict(completed=len(saved), planned=12, status="complete" if len(saved) == 12 else "incomplete")), flush=True)
    if args.prepare or args.status or len(saved) == 12:
        return 0
    if args.check:
        preflight(manifest)
        print(json.dumps(dict(status="local_checks_passed", api_calls=0)))
        return 0
    if saved and not args.resume:
        parser.error("Saved episodes exist; use --execute --resume")
    if not os.environ.get("DEEPSEEK_API_KEY"):
        parser.error("Set DEEPSEEK_API_KEY in this terminal; do not paste it into chat")
    spent = sum(record["cost_usd"] for record in saved.values())
    if spent >= COST_STOP_USD:
        parser.error("Recorded cost stop reached; no further API calls")
    preflight(manifest)
    for row in plan():
        if row["plan_index"] in saved:
            continue
        if spent >= COST_STOP_USD:
            print(json.dumps(dict(status="recorded_cost_stop", spent_usd=spent)), flush=True)
            return 2
        started = time.perf_counter()
        record = run_episode(MODEL, 0.0, TASK, row["variation"], "easy", AGENT_LIMIT, row["condition"],
                             environment_max_steps=row["environment_max_steps"])
        record.update(row, schema_version=1, timestamp_utc=datetime.now(timezone.utc).isoformat(),
                      variation_split="dev", suite="scienceworld-budget-dev-3", thinking="disabled",
                      budget_manifest_sha256=manifest_sha, runner_ms=round((time.perf_counter() - started) * 1000))
        # A protocol mismatch must not silently discard a paid outcome.
        append_jsonl(args.results, record)
        saved = saved_records(args.results, manifest_sha)
        spent += record["cost_usd"]
        print(json.dumps(dict(completed=len(saved), planned=12, task_id=record["task_id"],
                              condition=row["condition"], environment_max_steps=row["environment_max_steps"],
                              success=record["success"], score=record["score"], spent_usd=spent)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
