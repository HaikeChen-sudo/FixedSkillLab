"""Read and check the metrics release without models, API keys or benchmarks."""

import argparse
import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent


def read_rows(directory=HERE):
    return [json.loads(line) for line in (Path(directory) / "episodes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_rows(rows, schema):
    seen = set()
    for row in rows:
        if set(row) != set(schema["properties"]):
            raise ValueError("Unexpected or missing release fields")
        key = (row["batch_id"], row["task_id"], row["condition"], row["repeat"])
        if key in seen:
            raise ValueError("Duplicate episode key: " + str(key))
        seen.add(key)
        for name, spec in schema["properties"].items():
            value = row[name]
            types = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
            kind = {type(None): "null", bool: "boolean", int: "integer", float: "number", str: "string", list: "array"}.get(type(value))
            if kind not in types and not (kind == "integer" and "number" in types):
                raise ValueError("Invalid type: " + name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if not math.isfinite(value) or ("minimum" in spec and value < spec["minimum"]):
                    raise ValueError("Invalid number: " + name)
            if isinstance(value, list) and not all(isinstance(v, str) for v in value):
                raise ValueError("Expected string list: " + name)
        if row["total_tokens"] != row["input_tokens"] + row["output_tokens"]:
            raise ValueError("Token sum mismatch")
        if row["end_to_end_ms"] != row["runner_ms"]:
            raise ValueError("End-to-end time must not substitute legacy latency")
        if row["trace_event_count"] != row["tool_calls"]:
            raise ValueError("Trace and tool count differ")
        if row["environment"] == "scienceworld" and row["success"] != (row["score"] == 100):
            raise ValueError("ScienceWorld outcome inconsistent with score")
    return len(seen)


def mean_complete(rows, field):
    values = [r[field] for r in rows]
    return sum(values) / len(values) if values and all(v is not None for v in values) else None


def summaries(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["batch_id"], row["condition"])].append(row)
    output = []
    for (batch, condition), group in sorted(groups.items()):
        successes = sum(r["success"] for r in group)
        costs = [r["cost_usd"] for r in group]
        output.append({
            "batch_id": batch, "condition": condition, "episodes": len(group),
            "successes": successes, "task_success_rate": successes / len(group),
            "average_input_tokens": mean_complete(group, "input_tokens"),
            "average_output_tokens": mean_complete(group, "output_tokens"),
            "average_total_tokens": mean_complete(group, "total_tokens"),
            "average_end_to_end_ms": mean_complete(group, "end_to_end_ms"),
            "end_to_end_observed": sum(r["end_to_end_ms"] is not None for r in group),
            "average_legacy_latency_ms": mean_complete(group, "legacy_latency_ms"),
            "cost_per_successful_task_usd": sum(costs) / successes if successes and all(c is not None for c in costs) else None,
            "average_tool_calls": mean_complete(group, "tool_calls"),
            "average_score": mean_complete(group, "score"),
        })
    return output


def paired(rows, batch, left, right):
    if left == right:
        raise ValueError("Choose two different conditions")
    def index(condition):
        selected = [r for r in rows if r["batch_id"] == batch and r["condition"] == condition]
        found = {(r["task_id"], r["repeat"]): r for r in selected}
        if len(found) != len(selected):
            raise ValueError("Duplicate pairing keys")
        return found
    a, b = index(left), index(right)
    if not a or a.keys() != b.keys():
        raise ValueError("Missing or unequal paired coverage; refusing an inner join")
    return [{
        "task_id": k[0], "repeat": k[1], "left_success": a[k]["success"], "right_success": b[k]["success"],
        "right_minus_left_total_tokens": b[k]["total_tokens"] - a[k]["total_tokens"],
        "same_skill_prompt": a[k]["skill_prompt_sha256"] == b[k]["skill_prompt_sha256"] if a[k]["skill_prompt_sha256"] and b[k]["skill_prompt_sha256"] else None,
    } for k in sorted(a)]


def check(directory=HERE):
    directory = Path(directory)
    checksums = json.loads((directory / "checksums.json").read_text(encoding="utf-8"))
    for filename, expected in checksums.items():
        path = (directory / filename).resolve()
        if directory.resolve() not in path.parents:
            raise ValueError("Checksum path escapes release directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Checksum mismatch: " + filename)
    schema = json.loads((directory / "schema.json").read_text(encoding="utf-8"))
    rows = read_rows(directory)
    validate_rows(rows, schema)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if len(rows) != manifest["episodes"]:
        raise ValueError("Manifest count mismatch")
    for source in manifest["sources"]:
        group = [r for r in rows if r["batch_id"] == source["batch_id"]]
        if len(group) != source["episodes"] or len({r["task_id"] for r in group}) != source["tasks"]:
            raise ValueError("Batch coverage mismatch")
        expected = {(task, c, repeat) for task in {r["task_id"] for r in group} for c in source["conditions"] for repeat in source["repeats"]}
        if {(r["task_id"], r["condition"], r["repeat"]) for r in group} != expected:
            raise ValueError("Unbalanced batch")
        if any(r["source_sha256"] != source["sha256"] or r["source_file"] != source["path"] for r in group):
            raise ValueError("Source provenance mismatch")
    if {r["batch_id"] for r in rows} != {s["batch_id"] for s in manifest["sources"]}:
        raise ValueError("Unknown batch")
    con = sqlite3.connect((directory / "fixedskilllab.sqlite").resolve().as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or con.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("SQLite integrity or foreign keys failed")
        db_rows = {r["episode_id"]: dict(r) for r in con.execute("SELECT * FROM episodes")}
        if len(db_rows) != len(rows):
            raise ValueError("SQLite count differs from JSONL")
        for row in rows:
            actual = db_rows.get(row["episode_id"])
            expected = {k: v for k, v in row.items() if k != "skills_loaded"}
            if actual != expected:
                raise ValueError("SQLite values differ from JSONL")
            skills = [r[0] for r in con.execute("SELECT skill_name FROM loaded_skills WHERE episode_id=? ORDER BY position", (row["episode_id"],))]
            if skills != row["skills_loaded"]:
                raise ValueError("SQLite Skill order differs from JSONL")
        db_summary = [dict(r) for r in con.execute("SELECT * FROM condition_metrics ORDER BY batch_id,condition")]
        expected_summary = summaries(rows)
        if len(db_summary) != len(expected_summary):
            raise ValueError("SQLite summary count differs")
        for actual, expected in zip(db_summary, expected_summary):
            for k, v in expected.items():
                if isinstance(v, float):
                    if actual[k] is None or not math.isclose(actual[k], v, rel_tol=1e-12, abs_tol=1e-12):
                        raise ValueError("SQLite summary differs: " + k)
                elif actual[k] != v:
                    raise ValueError("SQLite summary differs: " + k)
    finally:
        con.close()
    return {"episodes": len(rows), "batches": len(manifest["sources"]), "failures": sum(not r["success"] for r in rows), "checks": "passed", "api_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--batch")
    parser.add_argument("--compare", nargs=2, metavar=("LEFT", "RIGHT"))
    args = parser.parse_args()
    try:
        result = check()
        if args.check:
            print(json.dumps(result))
            return
        rows = read_rows()
        if args.compare:
            if not args.batch:
                parser.error("--compare requires --batch")
            output = paired(rows, args.batch, *args.compare)
        else:
            output = summaries([r for r in rows if not args.batch or r["batch_id"] == args.batch])
            if not output:
                raise ValueError("Unknown batch")
        for row in output:
            print(json.dumps(row, ensure_ascii=False, allow_nan=False))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()

