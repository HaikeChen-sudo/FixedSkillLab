"""Derive task-family, median, and protocol checks for ScienceWorld v13b."""

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

from scienceworld_skills import GOLD_SKILLS, loaded_skill_text


ROOT = Path(__file__).resolve().parent
ANALYSIS_DIR = ROOT / "results" / "formal_scienceworld_v13b"
RECORDS = ANALYSIS_DIR / "scienceworld-v13b-oracle-mechanism-6x3.jsonl"
OUTPUT = ANALYSIS_DIR / "derived_analysis.json"
CONDITIONS = ("oracle_v3_full", "oracle_v3_metadata", "oracle_v3_placebo")


def average(rows, field):
    return mean(row[field] for row in rows)


def condition_summary(rows):
    return {
        "episodes": len(rows),
        "successes": sum(bool(row["success"]) for row in rows),
        "task_success_rate": mean(bool(row["success"]) for row in rows),
        "median_total_tokens": median(row["total_tokens"] for row in rows),
        "median_latency_ms": median(row["latency_ms"] for row in rows),
        "median_tool_calls": median(row["tool_calls"] for row in rows),
        "median_environment_moves": median(row["environment_moves"] for row in rows),
    }


def grouped_summary(records, field):
    grouped = defaultdict(list)
    for row in records:
        grouped[(row[field], row["condition"])].append(row)
    output = []
    for (group, condition), rows in sorted(grouped.items()):
        output.append({
            field: group,
            "condition": condition,
            "episodes": len(rows),
            "successes": sum(bool(row["success"]) for row in rows),
            "task_success_rate": mean(bool(row["success"]) for row in rows),
            "average_score": average(rows, "score"),
            "average_total_tokens": average(rows, "total_tokens"),
            "average_latency_ms": average(rows, "latency_ms"),
            "average_tool_calls": average(rows, "tool_calls"),
            "average_environment_moves": average(rows, "environment_moves"),
        })
    return output


def relative_reductions(records, control):
    full = [row for row in records if row["condition"] == "oracle_v3_full"]
    compared = [row for row in records if row["condition"] == control]
    fields = (
        "input_tokens", "output_tokens", "total_tokens", "latency_ms",
        "tool_calls", "environment_moves",
    )
    reductions = {
        field: 100 * (1 - average(full, field) / average(compared, field))
        for field in fields
    }
    reductions["median_total_tokens"] = 100 * (
        1 - median(row["total_tokens"] for row in full) / median(row["total_tokens"] for row in compared)
    )
    full_cost_per_success = sum(row["cost_usd"] for row in full) / sum(row["success"] for row in full)
    compared_cost_per_success = sum(row["cost_usd"] for row in compared) / sum(row["success"] for row in compared)
    reductions["cost_per_successful_task_usd"] = 100 * (1 - full_cost_per_success / compared_cost_per_success)
    return reductions


def protocol_checks(records):
    by_episode = defaultdict(dict)
    for row in records:
        by_episode[(row["task_name"], row["variation"], row["repeat"])][row["condition"]] = row
    same_gold_skill = all(
        len(rows) == len(CONDITIONS)
        and len({tuple(row["skills_loaded"]) for row in rows.values()}) == 1
        and next(iter(rows.values()))["skills_loaded"] == [GOLD_SKILLS[next(iter(rows.values()))["task_name"]]]
        for rows in by_episode.values()
    )
    word_counts = {}
    for task_name in ("boil", "freeze"):
        skill_name = GOLD_SKILLS[task_name]
        word_counts[skill_name] = {
            mode: len(loaded_skill_text([skill_name], "v3", mode).split())
            for mode in ("full", "metadata_only", "placebo")
        }
    return {
        "same_gold_skill_for_every_paired_episode": same_gold_skill,
        "models": sorted({row["model"] for row in records}),
        "temperatures": sorted({row["temperature"] for row in records}),
        "protocol_versions": sorted({row["agent_protocol_version"] for row in records}),
        "skill_library_versions": sorted({row["skill_library_version"] for row in records}),
        "max_steps": sorted({row["max_steps"] for row in records}),
        "render_modes": sorted({row["condition"]: row["skill_render_mode"] for row in records}.items()),
        "skill_prompt_word_counts": word_counts,
        "full_placebo_word_counts_match": all(
            counts["full"] == counts["placebo"] for counts in word_counts.values()
        ),
    }


def main():
    records = [json.loads(line) for line in RECORDS.read_text(encoding="utf-8").splitlines() if line.strip()]
    failures = Counter(
        (row["condition"], "budget_exhausted" if row["environment_moves"] >= row["max_steps"] else "other")
        for row in records if not row["success"]
    )
    output = {
        "condition_medians": {
            condition: condition_summary([row for row in records if row["condition"] == condition])
            for condition in CONDITIONS
        },
        "family_summary": grouped_summary(records, "task_name"),
        "task_summary": grouped_summary(records, "task_id"),
        "relative_reductions_full_vs_metadata_pct": relative_reductions(records, "oracle_v3_metadata"),
        "relative_reductions_full_vs_placebo_pct": relative_reductions(records, "oracle_v3_placebo"),
        "failures_by_condition_and_category": [
            {"condition": condition, "category": category, "failures": count}
            for (condition, category), count in sorted(failures.items())
        ],
        "protocol_checks": protocol_checks(records),
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "records": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
