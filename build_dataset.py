"""Build/check a fixed allowlisted metrics release; never call an LLM."""

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from datasets.v1.use_dataset import summaries, validate_rows

ROOT = Path(__file__).resolve().parent
RELEASE = ROOT / "datasets" / "v1"
SOURCE_COMMIT = "95d2e24"
# Explicit snapshots prevent new experiments from silently entering the release.
SOURCES = [
    ("alfworld_v5", "results/formal_v5/alfworld-v5-test-30x3.jsonl", "5af35e91fb510bbef295f5ba7ef1eab780742b02a8398f53547320f5b79c8b71", 450, 30),
    ("alfworld_v8", "results/formal_v8/alfworld-v8-confirm-20x3.jsonl", "210b2f05db7d85fa20210cda624677a37d2cb0059648aa4ae2079ebfb80cdecc", 180, 20),
    ("scienceworld_v11b", "results/formal_scienceworld_v11/scienceworld-v11b-confirm-18x3.jsonl", "fb46b8f603d68f9e4baea76de912d68d1edac54299018b3b3bd51b7923177956", 162, 18),
    ("scienceworld_v13b", "results/formal_scienceworld_v13b/scienceworld-v13b-oracle-mechanism-6x3.jsonl", "5e671e5c04d2e92a0041f8e5b74b0a0e89bfbaefd66c13a79314e904798a6692", 54, 6),
    ("semantic_top3", "results/scienceworld_strong_confirm_6x3.jsonl", "71770d89acce4fbcc0e691f32f352966cd8f68ff728624bded432382d8ad3103", 54, 6),
    ("semantic_top1_dev", "results/scienceworld_top1_pilot.jsonl", "4b2d306460a14ad20a4cc4b0b8d5397ef8d931ec32d5d4a3daa6fd06ece61ff4", 36, 4),
    ("content_dev", "results/scienceworld_content_dev/episodes.jsonl", "dd414a18ebffadafccac13583c503e3d002f8bc56dd3c163b75edbc4e4c7faae", 48, 4),
]

# Each field has a documented origin; free-text observations are never copied.
FIELDS = {
    "episode_id": ("string", False, "SHA-256 of JSON [batch_id, task_id, condition, repeat]."),
    "batch_id": ("string", False, "Release batch; comparisons must remain within batch."),
    "source_file": ("string", False, "Repository-relative source JSONL path."),
    "source_line": ("integer", False, "One-based physical line number in source JSONL."),
    "source_sha256": ("string", False, "SHA-256 of complete source file bytes."),
    "source_record_sha256": ("string", False, "SHA-256 of source line bytes excluding CR/LF."),
    "environment": ("string", False, "Original environment identifier."),
    "task_id": ("string", False, "Original identifier; not proof of identical initial state across batches."),
    "task_family": ("string", True, "Original task_family or ScienceWorld task_name."),
    "source_split": ("string", True, "Original variation_split or split; not a new dataset train/test split."),
    "run_id": ("string", False, "Original run identifier."),
    "condition": ("string", False, "Original condition name, without merging version suffixes."),
    "repeat": ("integer", False, "Original repeat index; repeated tasks are not independent tasks."),
    "timestamp_utc": ("string", False, "Original recorded timestamp, not guaranteed request start."),
    "model": ("string", False, "Requested model alias; provider backend snapshot is not known."),
    "temperature": ("number", False, "Recorded request temperature."),
    "thinking": ("string", True, "Recorded request setting, not a claim about hidden model internals."),
    "agent_protocol_version": ("string", True, "Original protocol label; not a full environment fingerprint."),
    "success": ("boolean", False, "Recorded environment outcome; not a model-judged label."),
    "score": ("number", True, "ScienceWorld final score; null for ALFWorld. Negative scores retained."),
    "input_tokens": ("integer", False, "Cumulative reported prompt tokens across calls."),
    "output_tokens": ("integer", False, "Cumulative reported completion tokens across calls."),
    "total_tokens": ("integer", False, "input_tokens + output_tokens; not context window size or FLOPs."),
    "prompt_cache_hit_tokens": ("integer", True, "Recorded cached input tokens."),
    "prompt_cache_miss_tokens": ("integer", True, "Recorded uncached input tokens."),
    "legacy_latency_ms": ("number", False, "Source latency_ms; scopes differ by runner version."),
    "runner_ms": ("number", True, "Original episode runner timer, when saved."),
    "end_to_end_ms": ("number", True, "Exactly runner_ms; never imputed from latency_ms."),
    "routing_ms": ("number", True, "Original routing timer, when saved."),
    "cost_usd": ("number", True, "Historical estimated episode cost, including failed completed episodes; not an invoice."),
    "llm_calls": ("integer", False, "Recorded model calls; interrupted unsaved attempts may be absent."),
    "tool_calls": ("integer", False, "Recorded tool calls; not always equal to simulator moves."),
    "environment_moves": ("integer", True, "Original simulator move count, when saved."),
    "environment_actions": ("integer", True, "Original agent action count, when saved."),
    "max_steps": ("integer", True, "Legacy budget setting; do not infer split budgets from it."),
    "agent_max_steps": ("integer", True, "Explicit agent budget only when present in source."),
    "environment_max_steps": ("integer", True, "Explicit environment budget only when present in source."),
    "initial_observation_sha256": ("string", True, "Recorded initial-observation fingerprint; not full hidden environment state."),
    "skills_loaded": ("array", False, "Ordered original loaded Skill identifiers, not Skill text."),
    "retriever": ("string", True, "Original retriever identifier; null can mean no retrieval."),
    "skill_library_version": ("string", True, "Original library version; not reconstructed from current code."),
    "skill_library_sha256": ("string", True, "Original library hash, when recorded."),
    "skill_prompt_sha256": ("string", True, "Original Skill-only prompt hash; not complete model prompt."),
    "skill_render_mode": ("string", True, "Original guidance rendering mode."),
    "termination_reason": ("string", True, "Original termination label, without inferred failure taxonomy."),
    "trace_event_count": ("integer", False, "Length of saved source trace; trace text is excluded from v1."),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def schema():
    props = {}
    for name, (kind, nullable, description) in FIELDS.items():
        item = {"type": [kind, "null"] if nullable else kind, "description": description}
        if kind in ("integer", "number") and name != "score":
            item["minimum"] = 0
        if kind == "array":
            item["items"] = {"type": "string"}
        props[name] = item
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FixedSkillLab v1 metrics episode", "type": "object", "additionalProperties": False, "required": list(props), "properties": props}


def normalize(raw, batch, path, line, file_hash, line_hash):
    row = {field: raw.get(field) for field in FIELDS}
    key = [batch, raw["task_id"], raw["condition"], raw["repeat"]]
    row.update(episode_id=sha(json.dumps(key, separators=(",", ":")).encode()), batch_id=batch,
               source_file=path, source_line=line, source_sha256=file_hash, source_record_sha256=line_hash,
               source_split=raw.get("variation_split", raw.get("split")), task_family=raw.get("task_family", raw.get("task_name")),
               legacy_latency_ms=raw["latency_ms"], end_to_end_ms=raw.get("runner_ms"), trace_event_count=len(raw["trace"]))
    return row


def csv_bytes(rows):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, bool)) else v for k, v in row.items()})
    return out.getvalue().encode("utf-8")



def sqlite_bytes(rows, sources):
    # A portable file needs neither a server nor an import process.
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "fixedskilllab.sqlite"
        con = sqlite3.connect(str(path))
        try:
            con.execute("PRAGMA foreign_keys=ON")
            con.execute("PRAGMA user_version=1")
            con.execute("CREATE TABLE batches (batch_id TEXT PRIMARY KEY, source_file TEXT NOT NULL, source_sha256 TEXT NOT NULL, episodes INTEGER NOT NULL, tasks INTEGER NOT NULL, conditions_json TEXT NOT NULL, repeats_json TEXT NOT NULL, source_splits_json TEXT NOT NULL, timestamp_min TEXT NOT NULL, timestamp_max TEXT NOT NULL)")
            names = [k for k in FIELDS if k != "skills_loaded"]
            columns = []
            for name in names:
                kind, nullable, _ = FIELDS[name]
                sql_type = {"string": "TEXT", "integer": "INTEGER", "number": "REAL", "boolean": "INTEGER"}[kind]
                item = name + " " + sql_type + ("" if nullable else " NOT NULL")
                if name == "episode_id":
                    item += " PRIMARY KEY"
                if kind == "boolean":
                    item += " CHECK (" + name + " IN (0,1))"
                if kind in ("integer", "number") and name != "score":
                    item += " CHECK (" + name + ">=0)"
                columns.append(item)
            columns.extend(["UNIQUE(batch_id,task_id,condition,repeat)", "FOREIGN KEY(batch_id) REFERENCES batches(batch_id)", "CHECK(total_tokens=input_tokens+output_tokens)", "CHECK(end_to_end_ms IS runner_ms)"])
            con.execute("CREATE TABLE episodes (" + ",".join(columns) + ")")
            con.execute("CREATE TABLE loaded_skills (episode_id TEXT NOT NULL REFERENCES episodes(episode_id), position INTEGER NOT NULL CHECK(position>=0), skill_name TEXT NOT NULL, PRIMARY KEY(episode_id,position))")
            con.execute("CREATE TABLE data_dictionary (table_name TEXT NOT NULL, column_name TEXT NOT NULL, json_type TEXT NOT NULL, nullable INTEGER NOT NULL, description TEXT NOT NULL, PRIMARY KEY(table_name,column_name))")
            con.execute("CREATE TABLE release_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            con.executemany("INSERT INTO release_metadata VALUES (?,?)", [("version", "1.0.0"), ("edition", "metrics-only"), ("source_commit", SOURCE_COMMIT), ("sqlite_build_version", sqlite3.sqlite_version), ("license", "MIT for project-owned material; see THIRD_PARTY.md")])
            for source in sources:
                con.execute("INSERT INTO batches VALUES (?,?,?,?,?,?,?,?,?,?)", (source["batch_id"], source["path"], source["sha256"], source["episodes"], source["tasks"], json.dumps(source["conditions"]), json.dumps(source["repeats"]), json.dumps(source["source_splits"]), source["timestamp_min"], source["timestamp_max"]))
            con.executemany("INSERT INTO episodes (" + ",".join(names) + ") VALUES (" + ",".join("?" for _ in names) + ")", [[r[k] for k in names] for r in rows])
            con.executemany("INSERT INTO loaded_skills VALUES (?,?,?)", [(r["episode_id"], i, name) for r in rows for i, name in enumerate(r["skills_loaded"])])
            con.executemany("INSERT INTO data_dictionary VALUES (?,?,?,?,?)", [("episodes", k, FIELDS[k][0], int(FIELDS[k][1]), FIELDS[k][2]) for k in names])
            con.executemany("INSERT INTO data_dictionary VALUES (?,?,?,?,?)", [("loaded_skills", "episode_id", "string", 0, "Foreign key to episodes."), ("loaded_skills", "position", "integer", 0, "Zero-based order in original skills_loaded list."), ("loaded_skills", "skill_name", "string", 0, "Original Skill identifier, not Skill text.")])
            batch_docs = {
                "batch_id": "Release batch identifier.",
                "source_file": "Repository-relative snapshot path.",
                "source_sha256": "SHA-256 of snapshot bytes.",
                "episodes": "Number of saved episodes in this batch.",
                "tasks": "Distinct source task identifiers, not independent sample count.",
                "conditions_json": "JSON array of original condition names.",
                "repeats_json": "JSON array of original repeat indices.",
                "source_splits_json": "JSON array of source split labels, not a new split.",
                "timestamp_min": "Earliest recorded episode timestamp.",
                "timestamp_max": "Latest recorded episode timestamp.",
            }
            con.executemany("INSERT INTO data_dictionary VALUES (?,?,?,?,?)", [("batches", k, "integer" if k in ("episodes", "tasks") else "string", 0, v) for k, v in batch_docs.items()])
            con.executemany("INSERT INTO data_dictionary VALUES (?,?,?,?,?)", [("release_metadata", "key", "string", 0, "Metadata name."), ("release_metadata", "value", "string", 0, "Metadata value as text.")])
            con.execute("CREATE INDEX episodes_task ON episodes(environment,task_id)")
            con.execute("CREATE INDEX episodes_condition ON episodes(batch_id,condition,success)")
            con.execute("CREATE INDEX loaded_skills_name ON loaded_skills(skill_name)")
            con.execute("""CREATE VIEW condition_metrics AS
                SELECT batch_id, condition, COUNT(*) AS episodes, SUM(success) AS successes,
                       AVG(success) AS task_success_rate,
                       AVG(input_tokens) AS average_input_tokens,
                       AVG(output_tokens) AS average_output_tokens,
                       AVG(total_tokens) AS average_total_tokens,
                       CASE WHEN COUNT(end_to_end_ms)=COUNT(*) THEN AVG(end_to_end_ms) END AS average_end_to_end_ms,
                       COUNT(end_to_end_ms) AS end_to_end_observed,
                       AVG(legacy_latency_ms) AS average_legacy_latency_ms,
                       CASE WHEN COUNT(cost_usd)=COUNT(*) AND SUM(success)>0 THEN SUM(cost_usd)/SUM(success) END AS cost_per_successful_task_usd,
                       AVG(tool_calls) AS average_tool_calls,
                       CASE WHEN COUNT(score)=COUNT(*) THEN AVG(score) END AS average_score
                FROM episodes GROUP BY batch_id, condition""")
            con.commit()
        finally:
            con.close()
        return path.read_bytes()

def build(root=ROOT):
    rows, sources = [], []
    for batch, path, expected_hash, count, tasks in SOURCES:
        data = (root / path).read_bytes()
        if sha(data) != expected_hash:
            raise ValueError("Source fingerprint changed: " + path)
        group = []
        for line_no, line in enumerate(data.splitlines(), 1):
            if line.strip():
                raw = json.loads(line)
                group.append(normalize(raw, batch, path, line_no, expected_hash, sha(line)))
        if len(group) != count or len({r["task_id"] for r in group}) != tasks:
            raise ValueError("Unexpected source coverage: " + path)
        rows.extend(group)
        sources.append({"batch_id": batch, "path": path, "sha256": expected_hash, "episodes": count, "tasks": tasks,
                        "conditions": sorted({r["condition"] for r in group}), "repeats": sorted({r["repeat"] for r in group}),
                        "source_splits": sorted({r["source_split"] for r in group}),
                        "timestamp_min": min(r["timestamp_utc"] for r in group), "timestamp_max": max(r["timestamp_utc"] for r in group)})
    validate_rows(rows, schema())
    rows.sort(key=lambda r: (r["batch_id"], r["task_id"], r["condition"], r["repeat"]))
    encoded = "".join(json.dumps(r, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n" for r in rows).encode()
    if re.search(rb'sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|/Users/|/home/|-----BEGIN .*PRIVATE KEY', encoded):
        raise ValueError("Possible secret or local path in release projection; values withheld")
    quality = {
        "episodes": len(rows), "failures": sum(not r["success"] for r in rows),
        "distinct_environment_task_ids": len({(r["environment"], r["task_id"]) for r in rows}),
        "duplicate_episode_keys": 0, "token_sum_mismatches": 0, "trace_call_mismatches": 0,
        "missing_by_field": {k: sum(r[k] is None for r in rows) for k in FIELDS},
        "by_batch": [{"batch_id": s["batch_id"], "episodes": s["episodes"],
                      "missing_by_field": {k: sum(r[k] is None for r in rows if r["batch_id"] == s["batch_id"]) for k in FIELDS}} for s in sources],
        "limitations": ["Only seven selected completed-record snapshots, not every attempted run.",
                        "82 environment/task identifiers do not establish 82 independent samples.",
                        "Null includes not recorded and not applicable; no imputation.",
                        "No raw observations, commands, model responses or Skill bodies in this release.",
                        "Checks establish saved-data consistency, not reproduction of the original experiments."],
    }
    manifest = {"dataset": "FixedSkillLab execution metrics", "version": "1.0.0", "edition": "metrics-only",
                "prepared_on": "2026-10-10", "source_repository": "https://github.com/HaikeChen-sudo/FixedSkillLab",
                "source_commit": SOURCE_COMMIT, "episodes": len(rows), "primary_key": ["batch_id", "task_id", "condition", "repeat"],
                "sources": sources, "builder_sha256": sha(Path(__file__).read_bytes()),
                "excluded_content": ["task instructions", "environment observations", "action commands", "model responses", "Skill bodies", "local paths", "API credentials"]}
    files = {"episodes.jsonl": encoded, "episodes.csv": csv_bytes(rows), "condition_summary.csv": csv_bytes(summaries(rows)),
             "schema.json": json_bytes(schema()), "manifest.json": json_bytes(manifest), "quality.json": json_bytes(quality),
             "LICENSE": (root / "LICENSE").read_bytes(), "fixedskilllab.sqlite": sqlite_bytes(rows, sources)}
    for name in ["README.md", "THIRD_PARTY.md", "use_dataset.py", "quickstart.ipynb", "queries.sql"]:
        files[name] = (root / "datasets" / "v1" / name).read_bytes()
    files["checksums.json"] = json_bytes({name: sha(data) for name, data in sorted(files.items())})
    return files


def archive_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo("fixedskilllab-metrics-1.0.0/" + name, date_time=(2026, 10, 10, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=RELEASE)
    parser.add_argument("--archive", type=Path, help="optional standalone ZIP; excludes raw source text")
    args = parser.parse_args()
    try:
        files = build()
        # Refuse to silently replace a release or partially overwrite old data.
        for name, data in files.items():
            target = args.output / name
            if target.exists() and target.read_bytes() != data:
                raise ValueError("Existing file differs; use a new output directory: " + str(target))
            if args.check and not target.is_file():
                raise ValueError("Missing release file: " + name)
        archive = archive_bytes(files) if args.archive else None
        if args.archive:
            if args.archive.exists() and args.archive.read_bytes() != archive:
                raise ValueError("Existing archive differs; choose a new path")
            if args.check and not args.archive.is_file():
                raise ValueError("Missing archive")
        if args.build:
            args.output.mkdir(parents=True, exist_ok=True)
            for name, data in files.items():
                if not (args.output / name).exists():
                    (args.output / name).write_bytes(data)
        if args.build and args.archive and not args.archive.exists():
            args.archive.parent.mkdir(parents=True, exist_ok=True)
            args.archive.write_bytes(archive)
        print(json.dumps({"mode": "check" if args.check else "build", "episodes": 984, "files": len(files), "api_calls": 0}))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()


