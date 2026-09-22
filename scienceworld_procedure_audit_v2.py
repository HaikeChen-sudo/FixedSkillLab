"""Post-holdout, read-only process checks for future ScienceWorld protocols.

Do not substitute these checks into the frozen Procedure holdout analysis.
"""

import re

from scienceworld_procedure_audit import TICKS


PLACEMENT = re.compile(r"^(?:move|put) (.+?) (?:to|on) inclined plane ([A-Z])$", re.I)
FOCUS = re.compile(r"^focus on inclined plane ([A-Z])$", re.I)
BOTTOM = re.compile(r"(?:at the bottom of the plane|approximately 100% down the plane)", re.I)
PRODUCT = re.compile(r"\bmix(?:es|ed)?\s+to\s+produce\b", re.I)


def chemistry_process(record):
    read = mix = focus = None
    for index, action in enumerate(record.get("trace", [])):
        result = action.get("result", {})
        if action.get("tool") != "act" or not result.get("ok"):
            continue
        observation = result.get("observation", "").lower()
        command = action.get("command", "").lower()
        if read is None and "recipe reads:" in observation:
            read = index
        if mix is None and PRODUCT.search(observation):
            mix = index
        if focus is None and command.startswith("focus on "):
            focus = index
    return {
        "read_index": read,
        "productive_mix_index": mix,
        "focus_index": focus,
        "read_mix_focus_order": None not in (read, mix, focus) and read < mix < focus,
    }


def incline_process(record):
    current = None
    complete = []
    focus_plane = None

    def finish_trial():
        if current and current["bottom"] and current["stopped"] and current["ticks"] is not None:
            complete.append({key: current[key] for key in ("plane", "object", "ticks")})

    for action in record.get("trace", []):
        result = action.get("result", {})
        if action.get("tool") != "act" or not result.get("ok"):
            continue
        command = " ".join(action.get("command", "").lower().split())
        placement = PLACEMENT.fullmatch(command)
        if placement:
            finish_trial()
            object_name = re.sub(r"^(?:the|a) ", "", placement.group(1))
            current = {"plane": placement.group(2).upper(), "object": object_name,
                       "running": False, "bottom": False, "stopped": False, "ticks": None}
            continue
        decision = FOCUS.fullmatch(command)
        if decision:
            finish_trial()
            focus_plane = decision.group(1).upper()
            break
        if current is None:
            continue
        if command == "activate stopwatch":
            current["running"] = True
        elif command == "deactivate stopwatch":
            current["stopped"] |= current["bottom"]
            current["running"] = False
        elif command == f'examine inclined plane {current["plane"].lower()}' and current["running"]:
            observation = result.get("observation", "").lower()
            current["bottom"] |= current["object"] in observation and bool(BOTTOM.search(observation))
        elif command == "examine stopwatch" and current["bottom"]:
            reading = TICKS.search(result.get("observation", ""))
            if reading:
                current["ticks"] = int(reading.group(1))
    else:
        finish_trial()

    last_by_plane = {trial["plane"]: trial for trial in complete}
    same_object = len({trial["object"] for trial in last_by_plane.values()}) == 1
    two_complete = len(last_by_plane) == 2 and same_object
    distinct_times = two_complete and len({trial["ticks"] for trial in last_by_plane.values()}) == 2
    description = (record.get("retrieval_query") or record.get("task_description") or "").lower()
    goals = [goal for goal in ("steepest", "shallowest") if f"{goal} angle" in description]
    goal = goals[0] if len(goals) == 1 else None
    choice_supported = None
    if distinct_times and focus_plane and goal:
        chosen = min if goal == "steepest" else max
        expected = chosen(last_by_plane.values(), key=lambda trial: trial["ticks"])["plane"]
        choice_supported = focus_plane == expected
    return {
        "complete_trials": complete,
        "same_object": same_object,
        "two_complete_trials": two_complete,
        "distinct_final_times": distinct_times,
        "goal": goal,
        "focus_plane": focus_plane,
        "choice_supported_by_times": choice_supported,
    }
