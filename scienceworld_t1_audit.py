"""Write the frozen T1 Skill-loading audit without calling an API."""

import argparse
import hashlib
import json
from pathlib import Path

from scienceworld_agent import skill_selection
from scienceworld_skills import T_HORIZONTAL_SKILL_NAME, T_VERTICAL_PATHS, loaded_skill_text
from scienceworld_suites import SCIENCEWORLD_T1_T_SHAPED_PILOT_12


CONDITIONS = ("no_skill", "t_horizontal", "t_vertical", "t_full")


def audit_rows():
    for task_name, variation in SCIENCEWORLD_T1_T_SHAPED_PILOT_12:
        for condition in CONDITIONS:
            selection = skill_selection(condition, task_name)
            prompt = loaded_skill_text(selection.names, selection.library_version) if selection.names else ""
            horizontal = T_HORIZONTAL_SKILL_NAME in selection.names
            vertical = any(name != T_HORIZONTAL_SKILL_NAME for name in selection.names)
            path = T_VERTICAL_PATHS[task_name] if vertical else ()
            yield {
                "task_id": f"{task_name}:v{variation:03d}",
                "task_name": task_name,
                "variation": variation,
                "condition": condition,
                "horizontal_layer_loaded": horizontal,
                "vertical_layer_loaded": vertical,
                "skills_loaded": selection.names,
                "skill_library_version": selection.library_version,
                "vertical_domain": path[0] if path else None,
                "vertical_path": list(path),
                "vertical_depth": len(path),
                "skill_prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest() if prompt else None,
                "skill_prompt_words": len(prompt.split()),
                "skill_prompt_characters": len(prompt),
            }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the frozen ScienceWorld T1 prompts; no API call")
    parser.add_argument("--output", type=Path, default=Path("results/scienceworld_t1_prompt_audit.jsonl"))
    args = parser.parse_args()
    rows = list(audit_rows())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "records": len(rows), "api_calls": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
