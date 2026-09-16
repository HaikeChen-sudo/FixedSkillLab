"""Validate and summarize the preregistered ScienceWorld T1 pilot."""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from result_utils import deduplicate_records
from scienceworld_suites import SCIENCEWORLD_T1_T_SHAPED_PILOT_12
from summarize_results import episode_metrics


CONDITIONS = ("no_skill", "t_horizontal", "t_vertical", "t_full")
STATE_CHANGE_TASKS = {"boil", "melt", "freeze"}


def success_interaction(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["condition"]].append(bool(row["success"]))
    missing = set(CONDITIONS) - set(grouped)
    if missing:
        raise ValueError(f"missing T1 conditions: {', '.join(sorted(missing))}")
    rates = {condition: mean(grouped[condition]) for condition in CONDITIONS}
    value = (rates["t_full"] - rates["t_vertical"]) - (
        rates["t_horizontal"] - rates["no_skill"]
    )
    return {"success_rates": rates, "interaction": value, "interaction_percentage_points": value * 100}


def validate_records(rows):
    expected = {
        (f"{task}:v{variation:03d}", condition, 0)
        for task, variation in SCIENCEWORLD_T1_T_SHAPED_PILOT_12
        for condition in CONDITIONS
    }
    actual = {(row["task_id"], row["condition"], row.get("repeat", 0)) for row in rows}
    errors = []
    if actual != expected:
        errors.append({
            "missing": sorted(expected - actual),
            "unexpected": sorted(actual - expected),
        })
    expected_factors = {
        "no_skill": (False, False),
        "t_horizontal": (True, False),
        "t_vertical": (False, True),
        "t_full": (True, True),
    }
    for row in rows:
        if row["condition"] not in expected_factors:
            errors.append({"task_id": row["task_id"], "unexpected_condition": row["condition"]})
            continue
        observed = (row.get("horizontal_layer_loaded"), row.get("vertical_layer_loaded"))
        if observed != expected_factors[row["condition"]]:
            errors.append({"task_id": row["task_id"], "condition": row["condition"], "factor_mismatch": observed})
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a complete ScienceWorld T1 pilot")
    parser.add_argument("results", type=Path, nargs="?", default=Path("results/scienceworld_results.jsonl"))
    parser.add_argument("--run-id", default="scienceworld-t1-t-shaped-pilot-12x1")
    parser.add_argument("--output", type=Path, default=Path("results/scienceworld_t1_analysis.json"))
    args = parser.parse_args()
    rows = [
        row
        for line in args.results.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in [json.loads(line)]
        if row.get("run_id") == args.run_id
    ]
    rows, duplicates_removed = deduplicate_records(rows)
    errors = validate_records(rows)
    if errors:
        raise ValueError(f"T1 result validation failed: {json.dumps(errors, ensure_ascii=False)}")
    strata = {
        "state_change_depth": [row for row in rows if row["task_name"] in STATE_CHANGE_TASKS],
        "cross_domain_breadth": [row for row in rows if row["task_name"] not in STATE_CHANGE_TASKS],
    }
    output = {
        "run_id": args.run_id,
        "episodes": len(rows),
        "duplicates_removed": duplicates_removed,
        "condition_metrics": {
            condition: episode_metrics([row for row in rows if row["condition"] == condition])
            for condition in CONDITIONS
        },
        "overall_success_interaction": success_interaction(rows),
        "stratum_success_interactions": {
            name: success_interaction(group) for name, group in strata.items()
        },
        "interpretation_limit": "Mechanism pilot on reused cases; effect direction only.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
