"""Freeze 12 new dev instances, collect task text, then run local MiniLM only."""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from scienceworld_hash_audit import digest
from scienceworld_retrieval import skill_text
from scienceworld_retrieval_baselines import MODEL_FILES, file_hash, local_encoder, ranked
from scienceworld_skills import GOLD_SKILLS, library_hash, loaded_skill_text, versioned_skills
from scienceworld_top1_audit import counts, write_new

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results/scienceworld_top1_new_dev_12"
SPLITS = ROOT / "results/scienceworld_top1_splits_2026-09-25.json"
BASELINE = ROOT / "results/scienceworld_retrieval_baselines_2026-09-24/summary.json"
MODEL = ROOT / ".models/all-MiniLM-L6-v2"
VERSION = "v3"
CODE = ("scienceworld_top1_dev_probe.py", "scienceworld_retrieval_baselines.py",
        "scienceworld_retrieval.py", "scienceworld_skills.py", "scienceworld_hash_audit.py",
        "scienceworld_top1_audit.py", "scienceworld_suites.py")


def seen_json(value, seen, query_hashes):
    if isinstance(value, dict):
        task, variation = value.get("task_name"), value.get("variation")
        if task in GOLD_SKILLS and type(variation) is int:
            seen.add((task, variation))
        for key, item in value.items():
            if key in ("retrieval_query", "query", "task_text", "task_description") and isinstance(item, str):
                query_hashes.add(digest(item.encode()))
            seen_json(item, seen, query_hashes)
    elif isinstance(value, list):
        if len(value) == 2 and isinstance(value[0], str) and value[0] in GOLD_SKILLS and type(value[1]) is int:
            seen.add(tuple(value))
        else:
            for item in value:
                seen_json(item, seen, query_hashes)
    elif isinstance(value, str):
        for task, variation in re.findall(r"([a-z-]+):v(\d+)", value):
            if task in GOLD_SKILLS:
                seen.add((task, int(variation)))


def history():
    from scienceworld_suites import SUITES

    seen = {pair for pairs in SUITES.values() for pair in pairs if pair[0] in GOLD_SKILLS}
    queries, files = set(), {}
    paths = sorted(set(ROOT.glob("*.py")) | set((ROOT / "docs").rglob("*.md"))
                   | set((ROOT / "results").rglob("*.json")) | set((ROOT / "results").rglob("*.jsonl")))
    for path in paths:
        if OUT in path.parents or path.name in (Path(__file__).name, "test_scienceworld_top1_dev_probe.py"):
            continue
        content = path.read_text(encoding="utf-8")
        files[str(path.relative_to(ROOT))] = digest(content.encode())
        if path.suffix == ".jsonl":
            for line in content.splitlines():
                if line.strip():
                    seen_json(json.loads(line), seen, queries)
        elif path.suffix == ".json":
            seen_json(json.loads(content), seen, queries)
        else:
            seen_json(content, seen, queries)
            for task, variation in re.findall(r"[\[(]\s*['\"]([a-z-]+)['\"]\s*,\s*(\d+)", content):
                if task in GOLD_SKILLS:
                    seen.add((task, int(variation)))
    return seen, queries, files


def choose_cases(splits, seen):
    cases = []
    for task in sorted(GOLD_SKILLS):
        split = splits[task]
        if set(split["dev"]) & (set(split["train"]) | set(split["test"])):
            raise ValueError("Official splits overlap")
        available = sorted(set(split["dev"]) - {v for t, v in seen if t == task})
        if len(available) < 2:
            raise ValueError("Fewer than two unused dev instances: " + task)
        cases.extend(dict(task_name=task, variation=v, task_id=f"{task}:v{v:03d}",
                          gold_skill=GOLD_SKILLS[task]) for v in available[:2])
    return cases


def prepare():
    if (OUT / "manifest.json").exists():
        raise ValueError("Manifest already frozen; do not reselect after inspecting queries")
    splits = json.loads(SPLITS.read_text())
    baseline = json.loads(BASELINE.read_text())
    if library_hash(VERSION) != baseline["library_hashes"][VERSION]:
        raise ValueError("Skill library changed")
    hashes = {name: file_hash(MODEL / name) for name in MODEL_FILES}
    if hashes != baseline["minilm"]["file_sha256"]:
        raise ValueError("Encoder files changed")
    seen, queries, sources = history()
    manifest = dict(schema_version=1, frozen_at_utc=datetime.now(timezone.utc).isoformat(),
                    selection_rule="all six original GOLD_SKILLS families; first two unseen official dev IDs per family",
                    cases=choose_cases(splits["tasks"], seen), library_version=VERSION,
                    library_sha256=library_hash(VERSION), simplification="easy",
                    splits_sha256=file_hash(SPLITS), baseline_sha256=file_hash(BASELINE),
                    minilm=baseline["minilm"], runtime={k: splits[k] for k in ("package_version", "jar_sha256")},
                    code_sha256={name: file_hash(ROOT / name) for name in CODE},
                    history_file_sha256=sources, historical_query_sha256=sorted(queries),
                    seen_cases=[list(pair) for pair in sorted(seen)],
                    history_scope="root Python, docs Markdown, results JSON/JSONL and registered suites; excludes tmp, binary reports and files outside project",
                    online_agent_changed=False, api_calls=0)
    write_new(OUT / "manifest.json", manifest)
    print(json.dumps(dict(status="frozen_before_query_collection", cases=manifest["cases"], api_calls=0)))


def verify():
    manifest = json.loads((OUT / "manifest.json").read_text())
    for name, expected in manifest["code_sha256"].items():
        if file_hash(ROOT / name) != expected:
            raise ValueError("Frozen code changed: " + name)
    if (file_hash(SPLITS) != manifest["splits_sha256"] or file_hash(BASELINE) != manifest["baseline_sha256"]
            or library_hash(VERSION) != manifest["library_sha256"]):
        raise ValueError("Split, baseline or Skill library changed")
    splits = json.loads(SPLITS.read_text())
    expected = choose_cases(splits["tasks"], {tuple(pair) for pair in manifest["seen_cases"]})
    if manifest["cases"] != expected:
        raise ValueError("Case selection differs from the frozen rule")
    return manifest


def collect(manifest):
    from importlib.metadata import version
    from scienceworld import ScienceWorldEnv
    from scienceworld.constants import JAR_PATH

    if (OUT / "queries.json").exists():
        raise ValueError("Queries already collected")
    if dict(package_version=version("scienceworld"), jar_sha256=file_hash(Path(JAR_PATH))) != manifest["runtime"]:
        raise ValueError("ScienceWorld runtime changed")
    frozen = json.loads(SPLITS.read_text())["tasks"]
    env = ScienceWorldEnv("", envStepLimit=1)
    queries = []
    try:
        # Verify every family's dev IDs before loading any newly selected task text.
        for task in sorted(GOLD_SKILLS):
            env.load(task, variationIdx=0, simplificationStr="easy")
            if sorted(env.get_variations_dev()) != sorted(frozen[task]["dev"]):
                raise ValueError("Official dev split changed: " + task)
        for case in manifest["cases"]:
            env.load(case["task_name"], variationIdx=case["variation"], simplificationStr="easy")
            _, info = env.reset()
            query = info["taskDesc"]
            if not isinstance(query, str) or not query.strip():
                raise ValueError("Empty task description")
            query_sha = digest(query.encode())
            queries.append(dict(case, query=query, query_sha256=query_sha,
                                previously_seen_query=query_sha in manifest["historical_query_sha256"]))
    finally:
        env.close()
    write_new(OUT / "queries.json", dict(manifest_sha256=file_hash(OUT / "manifest.json"), cases=queries,
                                        environment_actions=0, gold_paths_generated=0))
    print(json.dumps(dict(status="queries_collected", cases=len(queries), api_calls=0)))


def summary(rows):
    basic = counts(rows)
    for mode in ("flat", "body"):
        basic[mode + "_hit_at_3"] = sum(r["gold_rank"][mode] <= 3 for r in rows)
    basic["different_top3_set"] = sum(set(r["top3"]["flat"]) != set(r["top3"]["body"]) for r in rows)
    basic["different_top3_ordered"] = sum(r["top3"]["flat"] != r["top3"]["body"] for r in rows)
    basic["same_top1_prompt"] = sum(r["prompt_sha256"]["flat"]["1"] == r["prompt_sha256"]["body"]["1"] for r in rows)
    basic["same_top3_prompt"] = sum(r["prompt_sha256"]["flat"]["3"] == r["prompt_sha256"]["body"]["3"] for r in rows)
    return basic


def rank_queries(manifest):
    if (OUT / "audit.json").exists():
        raise ValueError("Audit exists; no automatic rerun or replacement")
    source = json.loads((OUT / "queries.json").read_text())
    if source["manifest_sha256"] != file_hash(OUT / "manifest.json"):
        raise ValueError("Query manifest mismatch")
    cases = source["cases"]
    if [{key: row[key] for key in ("task_name", "variation", "task_id", "gold_skill")} for row in cases] != manifest["cases"]:
        raise ValueError("Queries do not match the frozen case list")
    for row in cases:
        if digest(row["query"].encode()) != row["query_sha256"]:
            raise ValueError("Query hash mismatch")
    model, metadata = local_encoder(MODEL)
    if any(metadata[key] != manifest["minilm"][key] for key in ("file_sha256", "packages", "dimension", "max_seq_length")):
        raise ValueError("MiniLM files or runtime differ from the frozen baseline")
    skills = versioned_skills(VERSION)
    names = [skill.name for skill in skills]
    docs = {mode: [skill_text(skill, mode == "body") for skill in skills] for mode in ("flat", "body")}
    texts = sorted({row["query"] for row in cases} | set(docs["flat"]) | set(docs["body"]))
    lengths = {text: len(model.tokenizer(text.strip(), add_special_tokens=True, truncation=False)["input_ids"]) for text in texts}
    if any(n > model.max_seq_length for n in lengths.values()):
        raise ValueError("Input exceeds frozen token limit; no truncation or task replacement")
    vectors = dict(zip(texts, model.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False)))
    for row in cases:
        rankings = {mode: ranked(names, [vectors[text] @ vectors[row["query"]] for text in docs[mode]]) for mode in docs}
        row["ranking"] = rankings
        row["top1"] = {mode: ranking[0]["name"] for mode, ranking in rankings.items()}
        row["top3"] = {mode: [hit["name"] for hit in ranking[:3]] for mode, ranking in rankings.items()}
        row["gold_rank"] = {mode: next(hit["rank"] for hit in ranking if hit["name"] == row["gold_skill"]) for mode, ranking in rankings.items()}
        row["prompt_sha256"] = {mode: {str(k): digest(loaded_skill_text([hit["name"] for hit in ranking[:k]], VERSION).encode()) for k in (1, 3)} for mode, ranking in rankings.items()}
    unique = {(row["query_sha256"], row["gold_skill"]): row for row in cases}
    result = dict(manifest_sha256=file_hash(OUT / "manifest.json"), query_file_sha256=file_hash(OUT / "queries.json"),
                  library_version=VERSION, model=metadata, cases=cases, instance_summary=summary(cases),
                  unique_query_gold_summary=summary(list(unique.values())),
                  by_family={task: summary([r for r in cases if r["task_name"] == task]) for task in sorted(GOLD_SKILLS)},
                  previously_seen_query_instances=sum(row["previously_seen_query"] for row in cases),
                  embedding_input_tokens={digest(text.encode()): n for text, n in lengths.items()},
                  api_calls=0, agent_performance_measured=False,
                  decision="stop_identical_top1" if all(r["top1"]["flat"] == r["top1"]["body"] for r in cases) else "review_disagreements_before_any_agent_experiment")
    write_new(OUT / "audit.json", result)
    print(json.dumps({key: result[key] for key in ("instance_summary", "unique_query_gold_summary", "previously_seen_query_instances", "decision", "api_calls")}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "collect", "rank", "status"))
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    else:
        manifest = verify()
        if args.action == "collect":
            collect(manifest)
        elif args.action == "rank":
            rank_queries(manifest)
        else:
            print(json.dumps(dict(cases=manifest["cases"], queries_collected=(OUT / "queries.json").exists(),
                                  audit_complete=(OUT / "audit.json").exists(), api_calls=0)))


if __name__ == "__main__":
    main()
