"""Preview or execute the frozen 54-episode strong-router comparison."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import time

from scienceworld_agent import append_jsonl, make_env, run_episode
from scienceworld_retrieval_baselines import file_hash
from scienceworld_skills import V4_GOLD_SKILLS, library_hash, loaded_skill_text
from scienceworld_strong_retrieval import strong_retrieve


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "results/scienceworld_strong_confirmation_manifest.json"
RESULTS = ROOT / "results/scienceworld_strong_confirm_6x3.jsonl"
RUN_ID = "scienceworld-strong-confirm-6x3"
CASES = (
    ("chemistry-mix", 30),
    ("find-living-thing", 236),
    ("find-non-living-thing", 236),
    ("grow-plant", 96),
    ("inclined-plane-determine-angle", 132),
    ("power-component", 18),
)
CONDITIONS = ("no_skill", "semantic_flat_retrieval", "semantic_body_retrieval")
MODEL = "deepseek-v4-flash"
REPEATS = 3
MAX_STEPS = 100
ORDER_SEED = 20260924
COST_STOP_USD = 0.50


def settings():
    return dict(run_id=RUN_ID, cases=[list(case) for case in CASES],
                conditions=list(CONDITIONS), model=MODEL, temperature=0.0,
                thinking="disabled", simplification="easy", max_steps=MAX_STEPS,
                repeats=REPEATS, order_seed=ORDER_SEED, cost_stop_usd=COST_STOP_USD)


def episode_plan():
    rows = []
    for repeat in range(REPEATS):
        cases = list(CASES)
        random.Random(f"{ORDER_SEED}:tasks:{repeat}").shuffle(cases)
        for task, variation in cases:
            order = list(CONDITIONS)
            random.Random(f"{ORDER_SEED}:{task}:{variation}").shuffle(order)
            # Each condition occupies each serial position once across the three repeats.
            order = order[repeat:] + order[:repeat]
            for position, condition in enumerate(order):
                rows.append(dict(task_name=task, variation=variation, repeat=repeat,
                                 condition=condition, order_position=position, plan_index=len(rows)))
    return rows


def episode_key(row):
    return tuple(row[name] for name in ("task_name", "variation", "repeat", "condition"))


def verify_manifest():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["settings"] != settings() or manifest["episode_plan"] != episode_plan():
        raise ValueError("confirmation settings or episode order changed; do not reuse this run ID")
    for name, expected in manifest["file_sha256"].items():
        if file_hash(ROOT / name) != expected:
            raise ValueError(f"frozen confirmation file changed: {name}")
    for version, expected in manifest["library_sha256"].items():
        if library_hash(version) != expected:
            raise ValueError(f"frozen Skill library changed: {version}")
    return manifest, file_hash(MANIFEST)


def check_environment(manifest):
    from importlib.metadata import version
    from scienceworld.constants import JAR_PATH
    import scienceworld.scienceworld as wrapper

    actual = dict(package_version=version("scienceworld"), jar_sha256=file_hash(Path(JAR_PATH)),
                  wrapper_sha256=file_hash(Path(wrapper.__file__)))
    if actual != manifest["scienceworld_runtime"]:
        raise ValueError("ScienceWorld runtime differs from the frozen split check")
    env = make_env(1)
    try:
        for task, variation in CASES:
            # Only train v000 is loaded here; no candidate task text or Gold path is inspected.
            env.load(task, variationIdx=0, simplificationStr="easy")
            official = sorted(env.get_variations_test())
            if official != manifest["official_test_variations"][task] or variation not in official:
                raise ValueError(f"official test split mismatch: {task}:v{variation:03d}")
    finally:
        env.close()
    # Reuse the already-seen smoke query to check the isolated local encoder before any API call.
    strong_retrieve("Compare inclined plane B and inclined plane F.", True, "v4d", "minilm")


def validate_record(record, expected, manifest_sha):
    from hashlib import sha256

    fixed = dict(expected, run_id=RUN_ID, environment="scienceworld", model=MODEL,
                 temperature=0.0, thinking="disabled", simplification="easy", max_steps=MAX_STEPS,
                 suite="scienceworld-strong-confirm-6", variation_split="test", order_seed=ORDER_SEED,
                 confirmation_manifest_sha256=manifest_sha,
                 task_id=f"{expected['task_name']}:v{expected['variation']:03d}")
    if any(record.get(key) != value for key, value in fixed.items()):
        raise ValueError("incompatible episode or resume record")
    new_family = expected["task_name"] in V4_GOLD_SKILLS
    if (record.get("agent_protocol_version") != ("scienceworld-v14b" if new_family else "scienceworld-v2")
            or record.get("shared_controller_version") != ("shared-state-checkpoint-v1" if new_family else None)):
        raise ValueError("Agent/controller version changed")
    for key in ("input_tokens", "output_tokens", "total_tokens", "latency_ms", "routing_ms", "runner_ms", "cost_usd"):
        value = record.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"missing or invalid accounting value: {key}")
    if record["total_tokens"] != record["input_tokens"] + record["output_tokens"]:
        raise ValueError("token totals do not reconcile")
    if not isinstance(record.get("success"), bool) or record["success"] != (record["score"] >= 100):
        raise ValueError("success must match the environment score")
    names = record.get("skills_loaded")
    if expected["condition"] == "no_skill":
        if names != [] or record.get("skill_library_version") is not None or record.get("skill_prompt_sha256") is not None:
            raise ValueError("No Skill must load no Skill")
        return
    version = "v4d" if new_family else "v3"
    if not isinstance(names, list) or len(names) != 3 or len(set(names)) != 3:
        raise ValueError("retrieval must load exactly three distinct Skills")
    metadata = record.get("retrieval_metadata") or {}
    mode = "flat" if expected["condition"] == "semantic_flat_retrieval" else "body"
    if (record.get("skill_library_version") != version
            or record.get("skill_library_sha256") != library_hash(version)
            or metadata.get("index_mode") != mode or metadata.get("method") != "minilm"
            or metadata.get("truncated") is not False
            or metadata.get("library_sha256") != library_hash(version)
            or record.get("skill_render_mode") != "full"
            or names != [hit["name"] for hit in record.get("retrieval", [])]
            or record.get("skill_prompt_sha256") != sha256(loaded_skill_text(names, version).encode()).hexdigest()):
        raise ValueError("loaded Skills or retrieval metadata differ from the frozen protocol")


def completed_records(path, plan, manifest_sha):
    expected = {episode_key(row): row for row in plan}
    completed = {}
    if path.exists():
        with path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                if record.get("run_id") != RUN_ID:
                    raise ValueError(f"foreign run in dedicated result file, line {line_number}")
                key = episode_key(record)
                if key not in expected or key in completed:
                    raise ValueError(f"unexpected or duplicate episode: {key}")
                validate_record(record, expected[key], manifest_sha)
                completed[key] = record
    return completed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--execute", action="store_true", help="explicitly enable paid DeepSeek episodes")
    action.add_argument("--check", action="store_true", help="check local split/model only; no API")
    action.add_argument("--status", action="store_true", help="validate and count saved episodes; no API")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--results", type=Path, default=RESULTS)
    args = parser.parse_args(argv)
    if args.resume and not args.execute:
        parser.error("--resume requires --execute")
    manifest, manifest_sha = verify_manifest()
    plan = episode_plan()
    if args.check:
        check_environment(manifest)
        print(json.dumps(dict(status="local_checks_passed", api_calls=0, episodes_planned=len(plan))))
        return 0
    if not args.execute and not args.status:
        print(json.dumps(dict(status="preview_only", api_calls=0, settings=settings(),
                              episodes=len(plan), manifest_sha256=manifest_sha), ensure_ascii=False, indent=2))
        return 0
    completed = completed_records(args.results, plan, manifest_sha)
    spent = sum(record["cost_usd"] for record in completed.values())
    print(json.dumps(dict(status="complete" if len(completed) == len(plan) else "incomplete",
                          run_id=RUN_ID, completed=len(completed), planned=len(plan),
                          spent_usd=spent), ensure_ascii=False), flush=True)
    if args.status or len(completed) == len(plan):
        return 0
    if completed and not args.resume:
        parser.error("saved episodes exist; use --execute --resume")
    if spent >= COST_STOP_USD:
        print(json.dumps(dict(status="recorded_cost_stop", spent_usd=spent, threshold_usd=COST_STOP_USD)))
        return 2
    if not os.environ.get("DEEPSEEK_API_KEY"):
        parser.error("set DEEPSEEK_API_KEY in this terminal before --execute; do not paste the key into chat")
    check_environment(manifest)
    for row in plan:
        if episode_key(row) in completed:
            continue
        if spent >= COST_STOP_USD:
            print(json.dumps(dict(status="recorded_cost_stop", spent_usd=spent, threshold_usd=COST_STOP_USD)))
            return 2
        started = time.perf_counter()
        record = run_episode(MODEL, 0.0, row["task_name"], row["variation"], "easy", MAX_STEPS, row["condition"])
        record.update(row, run_id=RUN_ID, schema_version=1, timestamp_utc=datetime.now(timezone.utc).isoformat(),
                      suite="scienceworld-strong-confirm-6", variation_split="test", thinking="disabled",
                      order_seed=ORDER_SEED, confirmation_manifest_sha256=manifest_sha,
                      runner_ms=round((time.perf_counter() - started) * 1000))
        # Preserve even an invalid completed record, then stop; never silently discard a paid outcome.
        append_jsonl(args.results, record)
        validate_record(record, row, manifest_sha)
        completed[episode_key(row)] = record
        spent += record["cost_usd"]
        print(json.dumps(dict(run_id=RUN_ID, completed=len(completed), planned=len(plan),
                              task_id=record["task_id"], repeat=row["repeat"], condition=row["condition"],
                              success=record["success"], score=record["score"], spent_usd=spent),
                         ensure_ascii=False), flush=True)
    print(json.dumps(dict(status="complete", completed=len(completed), planned=len(plan), spent_usd=spent)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
