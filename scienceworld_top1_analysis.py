"""Reproduce the frozen Top-1 pilot analysis without model or environment calls."""

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

import scienceworld_top1_pilot as pilot

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "results/scienceworld_top1_analysis_2026-10-08.json"
MEASURES = ("input_tokens", "output_tokens", "total_tokens", "latency_ms", "runner_ms",
            "routing_ms", "tool_calls", "score", "environment_moves", "environment_actions",
            "controller_interventions")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate(rows):
    if not rows:
        raise ValueError("Cannot aggregate an empty group")
    successes = sum(r["success"] for r in rows)
    cost = sum(r["cost_usd"] for r in rows)
    result = dict(episodes=len(rows), successes=successes,
                  task_success_rate=successes / len(rows), cost_usd=cost,
                  cost_per_successful_task_usd=cost / successes if successes else None)
    result.update({"average_" + key: mean(r[key] for r in rows) for key in MEASURES})
    result["efficiency_per_1k_tokens"] = 1000 * successes / sum(r["total_tokens"] for r in rows)
    return result


def analyze(rows):
    expected = {(r["task_name"], r["variation"], r["condition"], r["repeat"]) for r in pilot.plan()}
    actual = [(r["task_name"], r["variation"], r["condition"], r["repeat"]) for r in rows]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("Analysis requires exactly the 36 distinct planned episodes")
    rows = sorted(rows, key=lambda r: r["plan_index"])
    for r in rows:
        if (len(r["trace"]) != r["tool_calls"] or not r["trace"]
                or r["trace"][-1]["result"]["score"] != r["score"]):
            raise ValueError("Trace accounting disagrees with episode metrics")
    summaries, families, tasks, repeats = [], [], [], []
    for condition in pilot.CONDITIONS:
        group = [r for r in rows if r["condition"] == condition]
        summaries.append(dict(condition=condition, **aggregate(group)))
        for family in sorted({r["task_name"] for r in group}):
            families.append(dict(condition=condition, task_name=family,
                                 **aggregate([r for r in group if r["task_name"] == family])))
        for task in sorted({r["task_id"] for r in group}):
            subset = [r for r in group if r["task_id"] == task]
            tasks.append(dict(condition=condition, task_id=task, skills_loaded=subset[0]["skills_loaded"],
                              **aggregate(subset)))
        per_repeat = [dict(repeat=i, **aggregate([r for r in group if r["repeat"] == i]))
                      for i in range(pilot.REPEATS)]
        keys = ["task_success_rate", "cost_per_successful_task_usd", "efficiency_per_1k_tokens"]
        keys += ["average_" + k for k in MEASURES]
        stats = {k: dict(mean=mean(r[k] for r in per_repeat), std=stdev(r[k] for r in per_repeat))
                 for k in keys if all(r[k] is not None for r in per_repeat)}
        repeats.append(dict(condition=condition, repeats=per_repeat, statistics=stats))
    paired = defaultdict(dict)
    for r in rows:
        paired[r["task_id"], r["repeat"]][r["condition"]] = r
    pairs = []
    for (task, repeat), group in sorted(paired.items()):
        flat, body = group["semantic_flat_top1"], group["semantic_body_top1"]
        pairs.append(dict(task_id=task, repeat=repeat,
                          same_skill_prompt=flat["skill_prompt_sha256"] == body["skill_prompt_sha256"],
                          same_initial_observation=flat["initial_observation_sha256"] == body["initial_observation_sha256"],
                          flat_success=flat["success"], body_success=body["success"],
                          body_minus_flat_total_tokens=body["total_tokens"] - flat["total_tokens"],
                          body_minus_flat_tool_calls=body["tool_calls"] - flat["tool_calls"],
                          body_minus_flat_runner_ms=body["runner_ms"] - flat["runner_ms"]))
    trace_rows = [dict(task_id=r["task_id"], repeat=r["repeat"], condition=r["condition"],
                       success=r["success"], score=r["score"], skills_loaded=r["skills_loaded"],
                       gold_skill_ranks=r["gold_skill_ranks"],
                       skill_prompt_sha256=r["skill_prompt_sha256"],
                       commands=[t.get("command") for t in r["trace"]]) for r in rows]
    return dict(schema_version=1, run_id=pilot.RUN_ID, episodes=len(rows), unique_tasks=len(pilot.CASES),
                independent_test=False, condition_summary=summaries, family_summary=families,
                task_summary=tasks, repeat_summary=repeats, body_flat_pairs=pairs,
                trace_commands=trace_rows,
                failures=[r for r in trace_rows if not r["success"]],
                metric_notes=dict(end_to_end="runner_ms includes environment creation and close",
                                  latency_ms="legacy scope excludes environment creation and close",
                                  cost="frozen historical accounting; not a verified provider bill",
                                  uncertainty="sample std across three repeats; not a confidence interval"))


def build_analysis():
    manifest = json.loads(pilot.MANIFEST.read_text())
    if manifest != pilot.current_manifest():
        raise ValueError("Frozen protocol or its source files changed")
    records = pilot.saved_records(pilot.RESULTS, manifest, sha(pilot.MANIFEST))
    result = analyze(list(records.values()))
    result["source_sha256"] = {str(p.relative_to(ROOT)): sha(p) for p in
                               (pilot.RESULTS, pilot.MANIFEST, Path(__file__))}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = build_analysis()
    content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output.exists():
        if args.output.read_text() != content:
            parser.error("Output differs; choose a new path instead of overwriting an analysis")
    else:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(content)
    print(json.dumps(dict(episodes=result["episodes"], unique_tasks=result["unique_tasks"],
                          failed_episodes=len(result["failures"]), api_calls=0, output=str(args.output))))


if __name__ == "__main__":
    main()
