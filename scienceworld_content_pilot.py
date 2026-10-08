"""Frozen four-arm content ablation; only --execute may call the paid model."""

import argparse
import fcntl
import json
import math
import os
import random
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from scienceworld_agent import FixedGuidance, append_jsonl, make_env, run_episode
from scienceworld_hash_audit import digest
from scienceworld_retrieval_baselines import file_hash
from scienceworld_skills import library_hash, loaded_skill_text, render, versioned_skills
from scienceworld_top1_audit import write_new
from scienceworld_top1_dev_probe import history, seen_json

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results/scienceworld_content_dev"
MANIFEST = OUT / "manifest.json"
QUERIES = OUT / "queries.json"
PREFLIGHT = OUT / "preflight.json"
RESULTS = OUT / "episodes.jsonl"
SPLITS = ROOT / "results/scienceworld_top1_splits_2026-09-25.json"
RUN_ID = "scienceworld-content-dev-4x3"
TASK = "find-non-living-thing"
CONDITIONS = ("no_skill", "content_correct", "content_mismatched", "content_pickup_required")
MODEL = "deepseek-v4-flash"
COUNT, REPEATS, LIMIT, SEED = 4, 3, 100, 20261008
COST_STOP_USD = 0.25
ORIGINAL_STEP = "Pick up or directly move the same object to the task's destination."
REQUIRED_STEP = "Pick up the same object before moving it to the task's destination."
CODE = ("agent.py", "scienceworld_agent.py", "scienceworld_content_pilot.py", "scienceworld_skills.py",
        "scienceworld_retrieval.py", "scienceworld_strong_retrieval.py", "scienceworld_hash_audit.py",
        "scienceworld_retrieval_baselines.py", "scienceworld_top1_dev_probe.py", "scienceworld_top1_audit.py",
        "scienceworld_suites.py", "docs/research/scienceworld_content_dev_protocol_2026-10-08.md")


def prompt_specs():
    skills = versioned_skills("v3")
    target = next(s for s in skills if s.name == "find-nonliving-object")
    if len(target.procedure) != 3 or target.procedure[2] != ORIGINAL_STEP:
        raise ValueError("Original movement instruction changed")
    changed = replace(target, procedure=target.procedure[:2] + (REQUIRED_STEP,))
    changed_hash = digest("\n".join(render(changed if s.name == target.name else s) for s in skills).encode())
    output = {}
    for condition in CONDITIONS:
        name = "find-living-object" if condition == "content_mismatched" else target.name
        prompt = ("" if condition == "no_skill" else render(changed) if condition == "content_pickup_required"
                  else loaded_skill_text([name], "v3"))
        output[condition] = dict(names=[] if not prompt else [name], prompt=prompt,
                                 prompt_sha256=digest(prompt.encode()) if prompt else None,
                                 library_version=None if not prompt else "content-pickup-v1" if condition == "content_pickup_required" else "v3",
                                 library_sha256=None if not prompt else changed_hash if condition == "content_pickup_required" else library_hash("v3"))
    return output


def choose_cases(split, seen):
    if any(set(split[a]) & set(split[b]) for a, b in (("train", "dev"), ("dev", "test"), ("train", "test"))):
        raise ValueError("Official split membership overlaps")
    available = sorted(set(split["dev"]) - {v for task, v in seen if task == TASK})
    if len(available) < COUNT:
        raise ValueError("Not enough unused dev instances; do not fall back to test")
    return [dict(task_name=TASK, variation=v, task_id=f"{TASK}:v{v:03d}") for v in available[:COUNT]]


def plan(cases):
    order = list(CONDITIONS)
    random.Random(SEED).shuffle(order)
    result = []
    for repeat in range(REPEATS):
        indexed = list(enumerate(cases))
        random.Random(f"{SEED}:{repeat}").shuffle(indexed)
        for case_index, case in indexed:
            shift = (case_index + repeat) % len(order)
            for position, condition in enumerate(order[shift:] + order[:shift]):
                result.append(dict(case, repeat=repeat, condition=condition, order_position=position,
                                   plan_index=len(result)))
    return result


def prepare():
    if MANIFEST.exists():
        raise ValueError("Manifest already exists; do not reselect after reading queries")
    seen, query_hashes, files = history()
    # The reused history scanner excludes its own old probe directory.
    prior = ROOT / "results/scienceworld_top1_new_dev_12/manifest.json"
    seen_json(json.loads(prior.read_text()), seen, query_hashes)
    files[str(prior.relative_to(ROOT))] = file_hash(prior)
    split = json.loads(SPLITS.read_text())["tasks"][TASK]
    cases = choose_cases(split, seen)
    runtime = json.loads((ROOT / "results/scienceworld_strong_confirmation_manifest.json").read_text())["scienceworld_runtime"]
    write_new(MANIFEST, dict(schema_version=1, run_id=RUN_ID, frozen_at_utc=datetime.now(timezone.utc).isoformat(),
              study_type="targeted_content_development_not_independent_test", cases=cases, episode_plan=plan(cases),
              conditions=list(CONDITIONS), model=MODEL, temperature=0.0, thinking="disabled", simplification="easy",
              agent_max_steps=LIMIT, environment_max_steps=LIMIT, repeats=REPEATS, order_seed=SEED,
              cost_stop_usd=COST_STOP_USD, prompts=prompt_specs(), scienceworld_runtime=runtime,
              selection_rule="first four unused official dev IDs of find-non-living-thing, before query collection",
              split_sha256=file_hash(SPLITS), seen_cases=[list(p) for p in sorted(seen)],
              historical_query_sha256=sorted(query_hashes), history_file_sha256=files,
              history_scope="root Python, docs Markdown, results JSON/JSONL and suites; excludes tmp, binary reports and external files",
              file_sha256={name: file_hash(ROOT / name) for name in CODE}))


def verify():
    manifest = json.loads(MANIFEST.read_text())
    settings = dict(run_id=RUN_ID, model=MODEL, temperature=0.0, thinking="disabled",
                    simplification="easy", agent_max_steps=LIMIT, environment_max_steps=LIMIT,
                    repeats=REPEATS, order_seed=SEED, cost_stop_usd=COST_STOP_USD,
                    conditions=list(CONDITIONS))
    if any(manifest.get(k) != v for k, v in settings.items()):
        raise ValueError("Frozen settings changed")
    for name, expected in manifest["file_sha256"].items():
        if file_hash(ROOT / name) != expected:
            raise ValueError("Frozen file changed: " + name)
    if file_hash(SPLITS) != manifest["split_sha256"] or manifest["prompts"] != prompt_specs():
        raise ValueError("Split or fixed prompts changed")
    cases = choose_cases(json.loads(SPLITS.read_text())["tasks"][TASK], {tuple(p) for p in manifest["seen_cases"]})
    if manifest["cases"] != cases or manifest["episode_plan"] != plan(cases):
        raise ValueError("Frozen selection or order differs from the registered rule")
    return manifest


def inspect_environment(manifest):
    from importlib.metadata import version
    from scienceworld.constants import JAR_PATH
    import scienceworld.scienceworld as wrapper

    runtime = dict(package_version=version("scienceworld"), jar_sha256=file_hash(Path(JAR_PATH)),
                   wrapper_sha256=file_hash(Path(wrapper.__file__)))
    if runtime != manifest["scienceworld_runtime"]:
        raise ValueError("Environment runtime changed")
    env = make_env(LIMIT)
    cases = []
    try:
        env.load(TASK, variationIdx=0, simplificationStr="easy")
        official = {name: sorted(getattr(env, "get_variations_" + name)()) for name in ("train", "dev", "test")}
        frozen = json.loads(SPLITS.read_text())["tasks"][TASK]
        if any(official[k] != sorted(frozen[k]) for k in official):
            raise ValueError("Live official split differs from the snapshot")
        for case in manifest["cases"]:
            env.load(TASK, variationIdx=case["variation"], simplificationStr="easy")
            observation, info = env.reset()
            query = info["taskDesc"]
            if not isinstance(query, str) or not query.strip():
                raise ValueError("Missing environment task description")
            query_sha = digest(query.encode())
            cases.append(dict(case, query=query, query_sha256=query_sha,
                              initial_observation_sha256=digest(observation.encode()),
                              previously_seen_query=query_sha in manifest["historical_query_sha256"]))
    finally:
        env.close()
    return dict(manifest_sha256=file_hash(MANIFEST), cases=cases, api_calls=0,
                environment_actions=0, gold_paths_generated=0)


def load_queries(manifest):
    queries = json.loads(QUERIES.read_text())
    check = json.loads(PREFLIGHT.read_text())
    if (queries["manifest_sha256"] != file_hash(MANIFEST) or check["manifest_sha256"] != file_hash(MANIFEST)
            or check["queries_sha256"] != file_hash(QUERIES)):
        raise ValueError("Query/preflight provenance changed")
    identities = [{k: r[k] for k in ("task_name", "variation", "task_id")} for r in queries["cases"]]
    if identities != manifest["cases"] or any(digest(r["query"].encode()) != r["query_sha256"] for r in queries["cases"]):
        raise ValueError("Frozen queries differ from the selected cases")
    return queries


def guidance(condition, query, manifest):
    spec = manifest["prompts"][condition]
    return FixedGuidance(condition, TASK, query, tuple(spec["names"]), spec["prompt"],
                         spec["library_version"], spec["library_sha256"])


def validate_record(row, expected, manifest, queries):
    spec = manifest["prompts"][expected["condition"]]
    query = next(r for r in queries["cases"] if r["task_id"] == expected["task_id"])
    fixed = dict(expected, run_id=RUN_ID, content_manifest_sha256=file_hash(MANIFEST),
                 content_queries_sha256=file_hash(QUERIES), model=MODEL, temperature=0.0, thinking="disabled",
                 environment="scienceworld", simplification="easy", variation_split="dev", max_steps=LIMIT,
                 agent_max_steps=LIMIT, environment_max_steps=LIMIT, agent_protocol_version="scienceworld-v2",
                 budget_protocol_version="split-budgets-v1", fixed_guidance_version="fixed-content-v1",
                 skills_loaded=spec["names"], skill_prompt_sha256=spec["prompt_sha256"],
                 skill_library_version=spec["library_version"], skill_library_sha256=spec["library_sha256"],
                 skill_render_mode="full" if spec["names"] else None, retrieval_query=query["query"],
                 retriever=None, retrieval_metadata=None, retrieval=[], gold_skill_ranks=[],
                 controller_interventions=0, shared_controller_version=None)
    if any(row.get(k) != v for k, v in fixed.items()):
        raise ValueError("Episode differs from frozen content protocol")
    if type(row.get("success")) is not bool or row["success"] != (row.get("score", -101) >= 100):
        raise ValueError("Success must come from environment score")
    for key in ("input_tokens", "output_tokens", "total_tokens", "latency_ms", "runner_ms", "routing_ms",
                "cost_usd", "tool_calls", "llm_calls", "pickup_command_count", "tool_error_count"):
        value = row.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("Invalid accounting: " + key)
    trace = row.get("trace", [])
    if (row["total_tokens"] != row["input_tokens"] + row["output_tokens"] or len(trace) != row["tool_calls"]
            or (trace and trace[-1]["result"]["score"] != row["score"])):
        raise ValueError("Token or trace accounting mismatch")
    if any(row[k] != v for k, v in trace_counts(trace).items()):
        raise ValueError("Action counters disagree with trace")


def trace_counts(trace):
    return dict(pickup_command_count=sum(" ".join((r.get("command") or "").lower().split()).startswith("pick up ") for r in trace),
                tool_error_count=sum(r["result"].get("ok") is False for r in trace))


def saved_records(manifest, queries):
    saved = {}
    if not RESULTS.exists():
        return saved
    for line in RESULTS.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        index = row.get("plan_index")
        if type(index) is not int or not 0 <= index < len(manifest["episode_plan"]) or index in saved:
            raise ValueError("Unexpected or duplicate episode; refusing resume")
        validate_record(row, manifest["episode_plan"][index], manifest, queries)
        saved[index] = row
    return saved


def execute(manifest, queries, resume):
    # Only this process may append paid outcomes to the experiment file.
    with (OUT / "execution.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another content experiment is running") from exc
        saved = saved_records(manifest, queries)
        if len(saved) == len(manifest["episode_plan"]):
            print(json.dumps(dict(status="complete", completed=len(saved))))
            return
        if saved and not resume:
            raise ValueError("Use --execute --resume to skip saved episodes")
        if not os.environ.get("DEEPSEEK_API_KEY"):
            raise ValueError("Set DEEPSEEK_API_KEY locally; do not paste it into chat")
        if inspect_environment(manifest) != queries:
            raise ValueError("Local preflight differs from frozen queries or initial observations")
        spent = sum(r["cost_usd"] for r in saved.values())
        for expected in manifest["episode_plan"]:
            if expected["plan_index"] in saved:
                continue
            if spent >= COST_STOP_USD:
                raise ValueError("Recorded cost stop reached; no further API calls")
            case = next(r for r in queries["cases"] if r["task_id"] == expected["task_id"])
            started = time.perf_counter()
            row = run_episode(MODEL, 0.0, TASK, expected["variation"], "easy", LIMIT, expected["condition"],
                              environment_max_steps=LIMIT, fixed_guidance=guidance(expected["condition"], case["query"], manifest))
            row.update(expected, run_id=RUN_ID, schema_version=1, thinking="disabled", variation_split="dev",
                       content_manifest_sha256=file_hash(MANIFEST), content_queries_sha256=file_hash(QUERIES),
                       timestamp_utc=datetime.now(timezone.utc).isoformat(), runner_ms=round((time.perf_counter() - started) * 1000),
                       **trace_counts(row["trace"]))
            append_jsonl(RESULTS, row)
            validate_record(row, expected, manifest, queries)
            saved[expected["plan_index"]] = row
            spent += row["cost_usd"]
            print(json.dumps(dict(completed=len(saved), planned=len(manifest["episode_plan"]), task_id=row["task_id"],
                                  condition=row["condition"], repeat=row["repeat"], success=row["success"], spent_usd=spent)), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    for action in ("prepare", "collect", "check", "status", "execute"):
        actions.add_argument("--" + action, action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    if args.resume and not args.execute:
        parser.error("--resume requires --execute")
    if not any((args.prepare, args.collect, args.check, args.status, args.execute)):
        print(json.dumps(dict(status="preview_only", planned=COUNT * len(CONDITIONS) * REPEATS, api_calls=0)))
        return 0
    if args.prepare:
        prepare()
    manifest = verify()
    if args.collect:
        if QUERIES.exists() or PREFLIGHT.exists():
            parser.error("Local collection already exists; preserve the original files")
        queries = inspect_environment(manifest)
        write_new(QUERIES, queries)
        write_new(PREFLIGHT, dict(manifest_sha256=file_hash(MANIFEST), queries_sha256=file_hash(QUERIES),
                                 status="local_environment_checked", api_calls=0, environment_actions=0))
    queries = load_queries(manifest) if QUERIES.exists() else None
    if args.check:
        if queries is None or inspect_environment(manifest) != queries:
            parser.error("Local check differs; collect once before running")
    if args.execute:
        if queries is None:
            parser.error("Run --collect locally before paid execution")
        execute(manifest, queries, args.resume)
    else:
        saved = saved_records(manifest, queries) if queries is not None else {}
        print(json.dumps(dict(run_id=RUN_ID, cases=manifest["cases"], planned=len(manifest["episode_plan"]),
                              completed=len(saved), local_queries_ready=queries is not None, api_calls=0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
