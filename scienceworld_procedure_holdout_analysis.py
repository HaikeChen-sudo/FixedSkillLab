"""Read-only, family-level analysis of the frozen Procedure holdout."""

import argparse
from collections import defaultdict
import json
from pathlib import Path

from scienceworld_incline_process_audit import inspect as inspect_incline
from scienceworld_procedure_audit import chemistry_events
from scienceworld_procedure_holdout import CASES, MANIFEST, REPEATS, SUITE, verify_manifest
from summarize_results import episode_metrics


def load_complete_run(path, run_id):
    manifest_hash = verify_manifest(MANIFEST)
    expected = {
        (name, variation, repeat, arm)
        for name, variation in CASES for repeat in range(REPEATS)
        for arm in ("procedure_p0", "procedure_p1")
    }
    rows = {}
    with path.open(encoding="utf-8") as source:
        for line in source:
            record = json.loads(line)
            if record.get("run_id") != run_id:
                continue
            key = (record.get("task_name"), record.get("variation"), record.get("repeat"), record.get("condition"))
            if key not in expected or key in rows:
                raise ValueError(f"unexpected or duplicate holdout episode: {key}")
            if record.get("suite") != SUITE or record.get("manifest_sha256") != manifest_hash:
                raise ValueError(f"foreign protocol record: {key}")
            if record["input_tokens"] + record["output_tokens"] != record["total_tokens"]:
                raise ValueError(f"token accounting mismatch: {key}")
            if record["success"] != (record["score"] >= 100):
                raise ValueError(f"environment success mismatch: {key}")
            rows[key] = record
    missing = expected - rows.keys()
    if missing:
        raise ValueError(f"holdout incomplete: {len(missing)} episodes missing")
    return rows


def process_result(record):
    if record["task_name"] == "chemistry-mix":
        return {"procedure_complete": chemistry_events(record)["read_mix_focus_order"]}
    audit = inspect_incline(record)
    return {
        "procedure_complete": audit["two_complete_trials"],
        "distinct_final_times": audit["distinct_final_times"],
        "choice_supported_by_times": audit["choice_supported_by_times"],
    }


def analyze(rows):
    groups = defaultdict(list)
    for (task_name, _variation, _repeat, arm), record in rows.items():
        groups[(task_name, arm)].append(record)
    summaries = []
    for (task_name, arm), records in sorted(groups.items()):
        process = [process_result(record) for record in records]
        summary = {
            "task_name": task_name, "condition": arm, "episodes": len(records),
            **episode_metrics(records),
            "procedure_complete_count": sum(item["procedure_complete"] for item in process),
            "procedure_complete_rate": sum(item["procedure_complete"] for item in process) / len(process),
        }
        if task_name == "inclined-plane-determine-angle":
            summary["distinct_final_times_count"] = sum(item["distinct_final_times"] for item in process)
            summary["choice_supported_count"] = sum(item["choice_supported_by_times"] is True for item in process)
            summary["choice_unassessable_count"] = sum(item["choice_supported_by_times"] is None for item in process)
        summaries.append(summary)
    paired = []
    for name, variation in CASES:
        pairs = [(rows[(name, variation, repeat, "procedure_p0")], rows[(name, variation, repeat, "procedure_p1")])
                 for repeat in range(REPEATS)]
        paired.append({
            "task_id": f"{name}:v{variation:03d}", "repeats": REPEATS,
            "success_difference_p1_minus_p0": sum(int(p1["success"]) - int(p0["success"]) for p0, p1 in pairs) / REPEATS,
            "procedure_difference_p1_minus_p0": sum(
                int(process_result(p1)["procedure_complete"]) - int(process_result(p0)["procedure_complete"])
                for p0, p1 in pairs
            ) / REPEATS,
            "average_total_token_difference_p1_minus_p0": sum(p1["total_tokens"] - p0["total_tokens"] for p0, p1 in pairs) / REPEATS,
        })
    return {"family_condition_summaries": summaries, "paired_by_variation": paired}


def main():
    parser = argparse.ArgumentParser(description="Analyze a complete Procedure holdout; no API call")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results", type=Path, default=Path(__file__).resolve().parent / "results/scienceworld_results.jsonl")
    args = parser.parse_args()
    print(json.dumps({"run_id": args.run_id, **analyze(load_complete_run(args.results, args.run_id))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
