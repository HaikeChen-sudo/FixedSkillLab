"""Post-hoc, read-only check of completed inclined-plane measurements."""

import argparse
import json
from pathlib import Path
import re

from scienceworld_procedure_audit import PLACEMENT, TICKS


BOTTOM = re.compile(r"wood block (?:at the bottom of the plane|approximately 100% down the plane)", re.I)
FOCUS = re.compile(r"^focus on inclined plane ([A-Z])$", re.I)
TASK_ID = "inclined-plane-determine-angle:v084"


def inspect(record):
    current = None
    complete = []
    focus_plane = None

    def finish_trial():
        if current and current["bottom"] and current["stopped"] and current["ticks"] is not None:
            complete.append({"plane": current["plane"], "ticks": current["ticks"]})

    for action in record["trace"]:
        result = action.get("result", {})
        if action.get("tool") != "act" or not result.get("ok"):
            continue
        command = " ".join(action.get("command", "").lower().split())
        placement = PLACEMENT.fullmatch(command)
        if placement:
            finish_trial()
            current = {"plane": placement.group(1).upper(), "running": False, "bottom": False, "stopped": False, "ticks": None}
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
            current["bottom"] |= bool(BOTTOM.search(result.get("observation", "")))
        elif command == "examine stopwatch" and current["bottom"]:
            reading = TICKS.search(result.get("observation", ""))
            if reading:
                current["ticks"] = int(reading.group(1))
    else:
        finish_trial()

    last_by_plane = {trial["plane"]: trial["ticks"] for trial in complete}
    two_complete = len(last_by_plane) == 2
    distinct_times = two_complete and len(set(last_by_plane.values())) == 2
    chosen_longer = focus_plane == max(last_by_plane, key=last_by_plane.get) if distinct_times and focus_plane else None
    return {
        "task_id": record["task_id"],
        "condition": record["condition"],
        "repeat": record.get("repeat", 0),
        "environment_success": record.get("score") == 100 and record.get("done") is True,
        "focus_plane": focus_plane,
        "complete_trials": complete,
        "two_complete_trials": two_complete,
        "distinct_final_times": distinct_times,
        "choice_supported_by_times": chosen_longer,
    }


def main():
    parser = argparse.ArgumentParser(description="Inspect full stopwatch trials; no API call")
    parser.add_argument("results", type=Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    rows = []
    seen = set()
    with args.results.open(encoding="utf-8") as source:
        for line in source:
            record = json.loads(line)
            if record.get("run_id") != args.run_id or record.get("task_id") != TASK_ID:
                continue
            key = (record["condition"], record.get("repeat", 0))
            if key in seen:
                raise ValueError(f"duplicate episode: {key}")
            seen.add(key)
            rows.append(inspect(record))
    if not rows:
        raise ValueError(f"no {TASK_ID} records for run_id={args.run_id}")
    for row in sorted(rows, key=lambda item: (item["repeat"], item["condition"])):
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
