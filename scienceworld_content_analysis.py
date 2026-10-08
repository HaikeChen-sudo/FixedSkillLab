"""Archive completed content ablation and inspect saved router interventions offline."""

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean, median, stdev

import scienceworld_content_pilot as content
import scienceworld_strong_confirmation as strong
import scienceworld_top1_analysis as top1

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "results/scienceworld_content_closeout_2026-10-08.json"
MEASURES = ("input_tokens", "output_tokens", "total_tokens", "runner_ms", "latency_ms", "tool_calls")


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def aggregate(rows):
    if not rows:
        raise ValueError("Empty analysis group")
    successes = sum(r["success"] for r in rows)
    cost = sum(r["cost_usd"] for r in rows)
    result = dict(episodes=len(rows), successes=successes, task_success_rate=successes / len(rows),
                  cost_usd=cost, cost_per_successful_task_usd=cost / successes if successes else None)
    result.update({"average_" + k: mean(r[k] for r in rows) for k in MEASURES})
    result.update(median_runner_ms=median(r["runner_ms"] for r in rows),
                  maximum_runner_ms=max(r["runner_ms"] for r in rows))
    return result


def content_analysis(rows, manifest, queries):
    plan = manifest["episode_plan"]
    indices = [r.get("plan_index") for r in rows]
    if len(rows) != 48 or any(type(i) is not int for i in indices) or set(indices) != set(range(48)):
        raise ValueError("Expected exactly 48 distinct content episodes")
    if manifest["run_id"] != content.RUN_ID or plan != content.plan(manifest["cases"]):
        raise ValueError("Saved content plan is inconsistent")
    query_by_task = {q["task_id"]: q for q in queries["cases"]}
    for r in rows:
        content.validate_record(r, plan[r["plan_index"]], manifest, queries)
        if not r.get("initial_observation_sha256") or r["initial_observation_sha256"] != query_by_task[r["task_id"]]["initial_observation_sha256"]:
            raise ValueError("Initial observation differs from frozen case")
    summaries, tasks, repeats = [], [], []
    for condition in content.CONDITIONS:
        group = [r for r in rows if r["condition"] == condition]
        summaries.append(dict(condition=condition, **aggregate(group),
                              average_pickup_commands=mean(r["pickup_command_count"] for r in group)))
        for task in sorted(query_by_task):
            subset = [r for r in group if r["task_id"] == task]
            tasks.append(dict(condition=condition, task_id=task, **aggregate(subset),
                              average_pickup_commands=mean(r["pickup_command_count"] for r in subset)))
        per_repeat = [dict(repeat=i, **aggregate([r for r in group if r["repeat"] == i])) for i in range(3)]
        fields = ["task_success_rate", "cost_per_successful_task_usd"] + ["average_" + k for k in MEASURES]
        repeats.append(dict(condition=condition, values=per_repeat,
                            statistics={k: dict(mean=mean(r[k] for r in per_repeat), std=stdev(r[k] for r in per_repeat))
                                        for k in fields if all(r[k] is not None for r in per_repeat)}))
    gate = movement_gate(tasks)
    outliers = [{k: r[k] for k in ("task_id", "condition", "repeat", "runner_ms", "tool_calls")}
                for r in sorted(rows, key=lambda r: r["runner_ms"], reverse=True)[:5]]
    return dict(run_id=content.RUN_ID, episodes=len(rows), independent_tasks=4, independent_test=False,
                condition_summary=summaries, task_summary=tasks, repeat_summary=repeats,
                movement_gate=gate, longest_episodes=outliers,
                initial_observation_matches=len(rows))


def movement_gate(task_summaries):
    comparisons = []
    for task in sorted({r["task_id"] for r in task_summaries}):
        groups = {r["condition"]: r for r in task_summaries if r["task_id"] == task}
        correct, required = groups["content_correct"], groups["content_pickup_required"]
        comparisons.append(dict(task_id=task,
            fewer_calls=correct["average_tool_calls"] < required["average_tool_calls"],
            fewer_pickup_commands=correct["average_pickup_commands"] < required["average_pickup_commands"],
            no_success_loss=correct["successes"] >= required["successes"]))
    count = sum(r["fewer_calls"] and r["fewer_pickup_commands"] for r in comparisons)
    passed = count >= 3 and all(r["no_success_loss"] for r in comparisons)
    return dict(required_instances=3, qualifying_instances=count, passed=passed,
                conclusion="direction_reproduced" if passed else "not_reproduced_or_tradeoff",
                comparisons=comparisons)


def router_comparison(rows, flat_name, body_name):
    pairs, tasks = [], []
    for task in sorted({r["task_id"] for r in rows}):
        subset = [r for r in rows if r["task_id"] == task]
        flat = [r for r in subset if r["condition"] == flat_name]
        body = [r for r in subset if r["condition"] == body_name]
        if len(flat) != 3 or len(body) != 3 or {r["repeat"] for r in flat} != {0, 1, 2} or {r["repeat"] for r in body} != {0, 1, 2}:
            raise ValueError("Router comparison requires complete three-repeat pairs")
        for f in flat:
            b = next(r for r in body if r["repeat"] == f["repeat"])
            if not f.get("skill_prompt_sha256") or not b.get("skill_prompt_sha256"):
                raise ValueError("Missing actual loaded prompt hash")
            fh, bh = f.get("initial_observation_sha256"), b.get("initial_observation_sha256")
            pairs.append(dict(task_id=task, repeat=f["repeat"],
                same_set=set(f["skills_loaded"]) == set(b["skills_loaded"]),
                same_order=f["skills_loaded"] == b["skills_loaded"],
                same_prompt=f["skill_prompt_sha256"] == b["skill_prompt_sha256"],
                same_initial_observation=(fh == bh) if fh and bh else None,
                flat_skills=f["skills_loaded"], body_skills=b["skills_loaded"],
                flat_success=f["success"], body_success=b["success"],
                flat_minus_body_tokens=f["total_tokens"] - b["total_tokens"]))
        tasks.append(dict(task_id=task, flat=aggregate(flat), body=aggregate(body)))
    decomposition = []
    for same in (True, False):
        group = [r for r in pairs if r["same_prompt"] == same]
        decomposition.append(dict(same_prompt=same, pairs=len(group),
                                  flat_minus_body_tokens=sum(r["flat_minus_body_tokens"] for r in group)))
    return dict(run_id=rows[0]["run_id"], paired_episodes=len(pairs),
                same_set_pairs=sum(r["same_set"] for r in pairs),
                same_order_pairs=sum(r["same_order"] for r in pairs),
                same_prompt_pairs=sum(r["same_prompt"] for r in pairs), pairs=pairs,
                token_decomposition=decomposition, task_summary=tasks,
                condition_summary=[dict(condition=c, **aggregate([r for r in rows if r["condition"] == c]))
                                   for c in sorted({r["condition"] for r in rows})])


def build_analysis():
    # Reading saved runs must not refresh prompts, start environments, or call a model.
    manifest = json.loads(content.MANIFEST.read_text())
    queries = content.load_queries(manifest)
    result = dict(schema_version=1, content=content_analysis(read_rows(content.RESULTS), manifest, queries))
    sm = json.loads(strong.MANIFEST.read_text())
    if sm["episode_plan"] != strong.episode_plan() or sm["settings"] != strong.settings():
        raise ValueError("Strong-router saved plan mismatch")
    saved = strong.completed_records(strong.RESULTS, sm["episode_plan"], top1.sha(strong.MANIFEST))
    if len(saved) != 54:
        raise ValueError("Expected 54 complete strong-router episodes")
    for version, expected in sm["library_sha256"].items():
        if strong.library_hash(version) != expected:
            raise ValueError("Restore the frozen Skill library to validate this historical run")
    top1.build_analysis()
    result["router_review"] = [
        router_comparison(list(saved.values()), "semantic_flat_retrieval", "semantic_body_retrieval"),
        router_comparison(read_rows(top1.pilot.RESULTS), "semantic_flat_top1", "semantic_body_top1")]
    sources = (content.RESULTS, content.MANIFEST, content.QUERIES, content.PREFLIGHT,
               strong.RESULTS, strong.MANIFEST, top1.pilot.RESULTS, top1.pilot.MANIFEST,
               Path(__file__), Path(content.__file__), Path(strong.__file__), Path(top1.__file__))
    result["source_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    result["notes"] = dict(end_to_end="runner_ms includes environment creation and close",
        cost="historical API estimate, not a verified bill", repeats="sample std, not confidence interval",
        scope="Runs remain separate; same-prompt differences do not establish a retrieval-mediated effect",
        initial_state="Missing hashes stay null; matching observations do not prove all hidden states match")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    result = build_analysis()
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output.exists():
        if args.output.read_text() != text:
            parser.error("Existing analysis differs; choose a new output path")
    else:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(text)
    print(json.dumps(dict(content_episodes=result["content"]["episodes"],
                          movement_gate=result["content"]["movement_gate"]["passed"],
                          api_calls=0, output=str(args.output))))


if __name__ == "__main__":
    main()
