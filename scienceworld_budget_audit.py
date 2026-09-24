"""Offline incline budget diagnosis. Never calls an LLM or replays test cases."""

import argparse
import hashlib
import json
from pathlib import Path

from scienceworld_procedure_audit_v2 import incline_process


TASK = "inclined-plane-determine-angle"
SEEN_CASES = ((0, "train"), (84, "dev"), (85, "dev"), (86, "dev"))
SOURCE = Path("results/scienceworld_strong_confirm_6x3.jsonl")
SOURCE_SHA = "71770d89acce4fbcc0e691f32f352966cd8f68ff728624bded432382d8ad3103"


def breakdown(record, initial_moves=0):
    buckets = {name: {"actions": 0, "moves": 0}
               for name in ("waiting", "observing", "other")}
    previous = initial_moves
    for action in record["trace"]:
        result = action.get("result", {})
        if "environment_moves" not in result:
            continue
        current = result["environment_moves"]
        if current < previous:
            raise ValueError("Environment moves decreased within an episode")
        command = action.get("command", "").lower().strip()
        category = ("waiting" if command.startswith("wait") else
                    "observing" if command.startswith(("examine ", "look", "inventory", "task"))
                    else "other")
        buckets[category]["actions"] += 1
        buckets[category]["moves"] += current - previous
        previous = current
    if previous != record["environment_moves"]:
        raise ValueError("Trace does not reconcile with final environment moves")
    return {"task_id": record["task_id"], "condition": record["condition"],
            "repeat": record.get("repeat"), "success": record["success"],
            "score": record["score"], "environment_moves": previous,
            "initial_moves": initial_moves, "steps": len(record["trace"]),
            "buckets": buckets, "process": incline_process(record)}


def gold_process(record):
    # Official paths use valid aliases absent from the older process parser.
    actions = []
    for action in record["trace"]:
        command = action["command"].replace("stopwatch in inventory", "stopwatch")
        if command.startswith("look at inclined plane "):
            command = command.replace("look at ", "examine ", 1)
        actions.append(dict(action, command=command))
    return incline_process(dict(record, trace=actions))


def replay(env, commands, limit):
    env.envStepLimit = limit
    observation, info = env.reset()
    initial = {"observation": observation, "score": info["score"], "moves": info["moves"]}
    trace = []
    done = False
    for command in commands:
        if done or len(trace) >= limit:
            break
        observation, reward, done, info = env.step(command)
        trace.append({"tool": "act", "command": command, "result": {
            "ok": True, "observation": observation, "reward": reward,
            "score": info["score"], "done": done, "environment_moves": info["moves"]}})
    reason = ("success" if info["score"] >= 100 else
              "environment_budget" if info["moves"] > limit else
              "environment_done" if done else
              "action_budget" if len(trace) >= limit else "path_exhausted")
    return {"limit": limit, "initial": initial, "success": info["score"] >= 100,
            "score": info["score"], "environment_moves": info["moves"],
            "termination_reason": reason, "trace": trace}


def same_prefix(left, right):
    # Only the wrapper's done flag should change when a budget cuts off a path.
    def physical_steps(record):
        return [(a["command"], {k: v for k, v in a["result"].items() if k != "done"})
                for a in record["trace"]]
    a, b = physical_steps(left), physical_steps(right)
    n = min(len(a), len(b))
    return left["initial"] == right["initial"] and a[:n] == b[:n]


def gold_dev_checks():
    from scienceworld_agent import make_env

    env = make_env(400)
    records = []
    try:
        for variation, split in SEEN_CASES:
            env.load(TASK, variationIdx=variation, simplificationStr="easy")
            if variation not in getattr(env, "get_variations_" + split)():
                raise ValueError(f"v{variation:03d} is not in {split}; refusing replay")
            env.load(TASK, variationIdx=variation, simplificationStr="easy", generateGoldPath=True)
            commands = list(env.get_gold_action_sequence())
            if not commands or any("ERROR" in command for command in commands):
                raise ValueError("Official reference path unavailable")
            task_id = f"{TASK}:v{variation:03d}"
            pair = []
            for limit in (100, 400):
                record = replay(env, commands, limit)
                record.update(task_id=task_id, condition="official_gold", split=split,
                              task_description=env.get_task_description(), simplification="easy")
                record["summary"] = breakdown(record, record["initial"]["moves"])
                record["summary"]["official_alias_normalized_process"] = gold_process(record)
                pair.append(record)
                print(json.dumps({"task_id": task_id, "limit": limit, "score": record["score"],
                                  "moves": record["environment_moves"], "actions": len(record["trace"])}), flush=True)
            matched = same_prefix(*pair)
            records.append({"task_id": task_id, "commands": commands,
                            "matched_initial_and_physical_prefix": matched, "runs": pair})
            if not matched:
                print("Replay differs: inspect saved traces before making a budget-only comparison.", flush=True)
    finally:
        env.close()
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-dev", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; choose a new filename to preserve evidence")
    source_bytes = SOURCE.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != SOURCE_SHA:
        raise ValueError("Frozen confirmation results changed")
    rows = [json.loads(line) for line in source_bytes.splitlines() if line.strip()]
    incline = [r for r in rows if r["task_id"] == TASK + ":v132"]
    expected = {(condition, repeat) for condition in
                ("no_skill", "semantic_flat_retrieval", "semantic_body_retrieval") for repeat in range(3)}
    if len(incline) != 9 or {(r["condition"], r["repeat"]) for r in incline} != expected:
        raise ValueError("Incomplete or duplicate paired incline records")
    result = {"source": str(SOURCE), "source_sha256": SOURCE_SHA,
              "scope": "saved test traces only; live replay restricted to seen train/dev cases",
              "saved_trace_initial_moves_assumption": 0,
              "process_note": "Narrow command-pattern diagnostic, not a replacement success grader.",
              "saved_incline": [breakdown(r) for r in incline],
              "gold_dev": gold_dev_checks() if args.gold_dev else []}
    if args.gold_dev:
        import scienceworld
        from importlib.metadata import version
        root = Path(scienceworld.__file__).parent
        result["runtime"] = {"scienceworld": version("scienceworld"), "files": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.suffix == ".jar" or p.name == "scienceworld.py"}}
    result["audit_code_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(args.output), "saved_episodes": len(incline),
                      "gold_cases": len(result["gold_dev"])}))


if __name__ == "__main__":
    main()
