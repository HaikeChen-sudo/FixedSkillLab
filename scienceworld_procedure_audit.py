"""Check two Procedure-only dev arms and classify existing ScienceWorld actions.

This is an offline, read-only check. It does not run Agent episodes or call an API.
"""

import argparse
from dataclasses import fields, replace
import hashlib
import json
from pathlib import Path
import re

from scienceworld_skills import render, versioned_skills


DEV_TASKS = ("chemistry-mix:v016", "inclined-plane-determine-angle:v084")
INCLINE_P1_STEP = (
    "Repeat the same experiment on the second plane. With the same block, "
    "compare the two measured travel times before selecting a plane."
)
PLACEMENT = re.compile(r"^(?:move|put) wood block (?:to|on) inclined plane ([A-Z])$", re.I)
TICKS = re.compile(r"time reads (\d+) ticks?", re.I)


def changed_fields(left, right):
    return [field.name for field in fields(left) if getattr(left, field.name) != getattr(right, field.name)]


def procedure_arms():
    v4 = {item.name: item for item in versioned_skills("v4")}
    v4b = {item.name: item for item in versioned_skills("v4b")}
    if v4.keys() != v4b.keys():
        raise ValueError("v4 and v4b contain different Skill names")
    library_diff = {name: changed_fields(v4[name], v4b[name]) for name in v4 if v4[name] != v4b[name]}
    if library_diff != {"chemistry-recipe-mix": ["procedure"]}:
        raise ValueError(f"chemistry P0/P1 is not Procedure-only: {library_diff}")

    incline_p0 = v4b["measure-inclined-plane-angle"]
    incline_p1 = replace(
        incline_p0,
        procedure=incline_p0.procedure[:2] + (INCLINE_P1_STEP,) + incline_p0.procedure[3:],
    )
    pairs = (
        (DEV_TASKS[0], v4["chemistry-recipe-mix"], v4b["chemistry-recipe-mix"]),
        (DEV_TASKS[1], incline_p0, incline_p1),
    )
    summary = []
    for task_id, p0, p1 in pairs:
        diff = changed_fields(p0, p1)
        if diff != ["procedure"]:
            raise ValueError(f"{task_id} P0/P1 changed fields: {diff}")
        summary.append({
            "task_id": task_id,
            "skill": p0.name,
            "changed_fields": diff,
            "p0_procedure": list(p0.procedure),
            "p1_procedure": list(p1.procedure),
            "p0_sha256": hashlib.sha256(render(p0).encode("utf-8")).hexdigest(),
            "p1_sha256": hashlib.sha256(render(p1).encode("utf-8")).hexdigest(),
        })
    return summary


def _actions(record):
    return [item for item in record.get("trace", []) if item.get("tool") == "act"]


def _score(action):
    return action.get("result", {}).get("score")


def chemistry_events(record):
    actions = _actions(record)
    read = mix = focus = None
    unproductive_mixes = 0
    previous_score = None
    for index, action in enumerate(actions):
        command = action.get("command", "").lower()
        observation = action.get("result", {}).get("observation", "").lower()
        score = _score(action)
        if read is None and command.startswith("read ") and "recipe reads:" in observation:
            read = index
        if command.startswith("mix "):
            if isinstance(score, (int, float)) and isinstance(previous_score, (int, float)) and score > previous_score:
                if mix is None:
                    mix = index
            else:
                unproductive_mixes += 1
        if focus is None and command.startswith("focus on "):
            focus = index
        if isinstance(score, (int, float)):
            previous_score = score
    return {
        "read_index": read,
        "productive_mix_index": mix,
        "focus_index": focus,
        "read_mix_focus_order": all(index is not None for index in (read, mix, focus)) and read < mix < focus,
        "unproductive_mix_attempts": unproductive_mixes,
    }


def incline_events(record):
    actions = _actions(record)
    current_plane = None
    placements = []
    readings = {}
    focus_index = None
    score_before_focus = None
    score_at_focus = None
    previous_score = None
    for index, action in enumerate(actions):
        command = action.get("command", "").lower()
        match = PLACEMENT.fullmatch(command)
        if match:
            current_plane = match.group(1).upper()
            placements.append(current_plane)
        if command == "examine stopwatch" and current_plane:
            tick_match = TICKS.search(action.get("result", {}).get("observation", ""))
            if tick_match:
                readings.setdefault(current_plane, []).append(int(tick_match.group(1)))
        if focus_index is None and command.startswith("focus on inclined plane "):
            focus_index = index
            score_before_focus = previous_score
            score_at_focus = _score(action)
            break
        if isinstance(_score(action), (int, float)):
            previous_score = _score(action)
    two_planes_timed = len(readings) >= 2
    milestone = isinstance(score_before_focus, (int, float)) and score_before_focus >= 50
    if focus_index is None:
        decision = "no_plane_focus"
    elif not (two_planes_timed and milestone):
        decision = "premature_focus"
    elif score_at_focus == 100:
        decision = "correct_after_milestone"
    else:
        decision = "wrong_after_milestone"
    return {
        "placements_before_focus": placements,
        "stopwatch_ticks_by_plane": readings,
        "two_planes_timed": two_planes_timed,
        "score_before_focus": score_before_focus,
        "score_at_focus": score_at_focus,
        "decision": decision,
    }


def audit_record(record):
    task_id = record["task_id"]
    if task_id not in DEV_TASKS:
        raise ValueError(f"not a registered dev task: {task_id}")
    actions = _actions(record)
    final = actions[-1].get("result", {}) if actions else {}
    return {
        "task_id": task_id,
        "condition": record["condition"],
        "environment_score": record.get("score"),
        "environment_success": record.get("score") == 100 and final.get("done") is True,
        "events": chemistry_events(record) if task_id == DEV_TASKS[0] else incline_events(record),
    }


def audit_file(path, run_id):
    rows = []
    seen = set()
    with path.open(encoding="utf-8") as source:
        for line in source:
            record = json.loads(line)
            if record.get("run_id") != run_id or record.get("task_id") not in DEV_TASKS:
                continue
            key = (record["task_id"], record["condition"])
            if key in seen:
                raise ValueError(f"duplicate dev task/condition: {key}")
            seen.add(key)
            rows.append(audit_record(record))
    if not rows:
        raise ValueError(f"no registered dev records for run_id={run_id}")
    return sorted(rows, key=lambda row: (row["task_id"], row["condition"]))


def main():
    parser = argparse.ArgumentParser(description="Read-only Procedure dev audit; no API call")
    parser.add_argument("results", type=Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps({
        "run_id": args.run_id,
        "api_calls": 0,
        "procedure_arms": procedure_arms(),
        "observed_records": audit_file(args.results, args.run_id),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
