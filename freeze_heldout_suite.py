"""Freeze a balanced ALFWorld held-out suite without calling an LLM."""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from alfworld_suites import ALFWORLD_V2_30, SUITES


FAMILIES = {
    "pick_heat_then_place_in_recep": "heat_then_place",
    "pick_clean_then_place_in_recep": "clean_then_place",
    "pick_cool_then_place_in_recep": "cool_then_place",
    "pick_two_obj_and_place": "two_object_place",
    "look_at_obj": "light_inspection",
    "pick_and_place_simple": "simple_pick_place",
}


def family_for_game(game_file):
    directory = Path(game_file).parents[1].name
    return next(family for prefix, family in FAMILIES.items() if directory.startswith(prefix))


def task_query(game_file):
    grammar = json.loads(Path(game_file).read_text(encoding="utf-8"))["grammar"]
    match = re.search(r'"task"\s*:\s*\[\s*\{\s*"rhs"\s*:\s*"([^"]+)"', grammar)
    if not match:
        raise ValueError(f"task text not found in {game_file}")
    return match.group(1)


def select_heldout(game_files, excluded, per_family=5):
    selected = defaultdict(list)
    for index, game_file in enumerate(game_files):
        family = family_for_game(game_file)
        if index not in excluded and len(selected[family]) < per_family:
            selected[family].append(index)
    if set(selected) != set(FAMILIES.values()) or any(len(indexes) != per_family for indexes in selected.values()):
        raise ValueError("could not select a balanced held-out suite")
    return tuple(index for family in FAMILIES.values() for index in selected[family])


def main():
    from alfworld.agents.environment import get_environment

    from alfworld_agent import environment_config
    from alfworld_gold_skills import gold_skills_for_game

    parser = argparse.ArgumentParser(description="Freeze 30 balanced held-out ALFWorld tasks")
    parser.add_argument("--data-dir", type=Path, default=Path(".alfworld-data"))
    parser.add_argument("--split", default="valid_unseen")
    parser.add_argument("--output", type=Path, default=Path("results/alfworld_v3_heldout_manifest.jsonl"))
    parser.add_argument("--run-id", default="alfworld-v3-heldout-offline")
    parser.add_argument("--exclude-suites", default="alfworld-v2-30", help="Comma-separated frozen suites to exclude")
    args = parser.parse_args()

    config = environment_config(args.data_dir, args.split, 50)
    source = get_environment("AlfredTWEnv")(config, train_eval="eval_out_of_distribution")
    excluded = set()
    for name in args.exclude_suites.split(","):
        if name not in SUITES:
            raise ValueError(f"unknown suite in --exclude-suites: {name}")
        excluded.update(SUITES[name])
    indexes = select_heldout(source.game_files, excluded)
    rows = []
    for index in indexes:
        game_file = source.game_files[index]
        rows.append({
            "run_id": args.run_id,
            "condition": "heldout_manifest",
            "repeat": 0,
            "task_id": f"{args.split}:{index:03d}",
            "task_index": index,
            "task_family": family_for_game(game_file),
            "game_file": game_file,
            "query": task_query(game_file),
            "gold_skills": list(gold_skills_for_game(game_file)),
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"run_id": args.run_id, "tasks": len(rows), "task_indexes": list(indexes), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
