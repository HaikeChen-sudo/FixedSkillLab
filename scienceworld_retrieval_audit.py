"""Audit frozen ScienceWorld retrieval queries without calling an LLM."""

import argparse
import json
from pathlib import Path

from scienceworld_agent import make_env, skill_selection
from scienceworld_suites import SUITES, SUITE_VARIATION_SPLITS


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an offline retrieval audit for one frozen ScienceWorld suite")
    parser.add_argument("--suite", choices=sorted(SUITES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--simplification", default="easy")
    args = parser.parse_args()

    rows = []
    env = make_env(1)
    try:
        for task_name, variation in SUITES[args.suite]:
            env.load(task_name, variationIdx=variation, simplificationStr=args.simplification)
            if variation not in env.get_variations_test():
                raise ValueError(f"{task_name}:v{variation:03d} is not in the official test split")
            _, info = env.reset()
            task_text = info["taskDesc"]
            flat = skill_selection("flat_retrieval", task_name, task_text)
            body = skill_selection("body_aware_retrieval", task_name, task_text)
            rows.append({
                "suite": args.suite,
                "variation_split": SUITE_VARIATION_SPLITS[args.suite],
                "task_id": f"{task_name}:v{variation:03d}",
                "task_name": task_name,
                "variation": variation,
                "task_text": task_text,
                "gold_skills": flat.gold_skills,
                "flat_top_3": flat.names,
                "flat_gold_rank": flat.gold_skill_ranks[0],
                "body_top_3": body.names,
                "body_gold_rank": body.gold_skill_ranks[0],
                "retriever": flat.retriever,
                "skill_library_version": flat.library_version,
            })
    finally:
        env.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps({
        "suite": args.suite,
        "tasks": len(rows),
        "flat_gold_hit_at_3": sum(row["flat_gold_rank"] is not None for row in rows) / len(rows),
        "body_gold_hit_at_3": sum(row["body_gold_rank"] is not None for row in rows) / len(rows),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
