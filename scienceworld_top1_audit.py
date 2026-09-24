"""Audit cached MiniLM Top-1 on official train/dev cases; no model/API calls."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from scienceworld_skills import library_hash, versioned_skills

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "results/scienceworld_retrieval_baselines_2026-09-24"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def collect_splits(tasks):
    from importlib.metadata import version
    from scienceworld import ScienceWorldEnv
    from scienceworld.constants import JAR_PATH

    env = ScienceWorldEnv("", envStepLimit=1)
    result = {}
    try:
        for task in sorted(tasks):
            # Loading train v000 exposes split metadata without reading new test tasks.
            env.load(task, variationIdx=0, simplificationStr="easy")
            result[task] = {split: list(getattr(env, "get_variations_" + split)())
                            for split in ("train", "dev", "test")}
            if 0 not in result[task]["train"]:
                raise ValueError("Expected v000 to be a training variation")
    finally:
        env.close()
    return dict(package_version=version("scienceworld"), jar_sha256=sha(Path(JAR_PATH)),
                acquisition="official get_variations_* after loading train v000; no actions or Gold paths",
                tasks=result)


def select_cases(rows, splits):
    selected, excluded = {}, Counter()
    for row in rows:
        task, variation = row["task_id"].rsplit(":v", 1)
        memberships = [name for name, values in splits[task].items() if int(variation) in values]
        if len(memberships) != 1:
            raise ValueError("Missing or overlapping official split membership")
        split = memberships[0]
        if split not in ("train", "dev"):
            excluded[split] += 1
            continue
        version, query = row["library_version"], row["query"]
        query_sha = hashlib.sha256(query.encode()).hexdigest()
        if row["library_sha256"] != library_hash(version) or row["query_sha256"] != query_sha:
            raise ValueError("Library or query hash mismatch")
        names = {skill.name for skill in versioned_skills(version)}
        if row["gold_skill"] not in names:
            raise ValueError("Gold is outside the frozen library")
        top = {}
        for mode in ("flat", "body"):
            comparison = row["comparisons"][mode]["minilm"]
            ranking = comparison["ranking"]
            if (len(ranking) != len(names) or {r["name"] for r in ranking} != names
                    or [r["rank"] for r in ranking] != list(range(1, len(names) + 1))):
                raise ValueError("Invalid cached full ranking")
            gold_rank = next(r["rank"] for r in ranking if r["name"] == row["gold_skill"])
            if gold_rank != comparison["gold_rank"]:
                raise ValueError("Cached Gold rank disagrees with ranking")
            top[mode] = ranking[0]["name"]
        case = dict(task_id=row["task_id"], split=split, library_version=version,
                    library_sha256=row["library_sha256"], query_sha256=query_sha,
                    query=query, gold_skill=row["gold_skill"], top1=top,
                    source_records=row["source_records"])
        key = (row["task_id"], version, query_sha)
        if key in selected and selected[key] != case:
            raise ValueError("Conflicting duplicate cached case")
        selected[key] = case
    return list(selected.values()), dict(excluded)


def counts(cases):
    result = dict(cases=len(cases), flat_hit=0, body_hit=0, different_top1=0,
                  both_hit=0, flat_only=0, body_only=0, both_miss=0)
    for row in cases:
        flat = row["top1"]["flat"] == row["gold_skill"]
        body = row["top1"]["body"] == row["gold_skill"]
        result["flat_hit"] += flat
        result["body_hit"] += body
        result["different_top1"] += row["top1"]["flat"] != row["top1"]["body"]
        result["both_hit" if flat and body else "flat_only" if flat else "body_only" if body else "both_miss"] += 1
    return result


def summarize(cases):
    groups = defaultdict(list)
    for row in cases:
        groups[row["library_version"]].append(row)
    output = []
    for version, group in sorted(groups.items()):
        unique = {}
        for row in group:
            key = (row["query_sha256"], row["gold_skill"])
            if key in unique and unique[key]["top1"] != row["top1"]:
                raise ValueError("Identical query/Gold has conflicting ranks")
            unique[key] = row
        output.append(dict(library_version=version, task_query_units=counts(group),
                           unique_query_gold=counts(list(unique.values()))))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits", type=Path, required=True)
    parser.add_argument("--collect-splits", action="store_true", help="local Java metadata only")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or (args.collect_splits and args.splits.exists()):
        parser.error("Output already exists; historical files are never overwritten")
    manifest = json.loads((CACHE / "summary.json").read_text())
    for name, expected in manifest["output_sha256"].items():
        if sha(CACHE / name) != expected:
            raise ValueError("Cached audit output changed: " + name)
    if any(value["truncated"] for value in manifest["truncation"].values()):
        raise ValueError("Cached embeddings contain truncated inputs")
    rows = [json.loads(line) for line in (CACHE / "rankings.jsonl").read_text().splitlines() if line.strip()]
    if args.collect_splits:
        write_new(args.splits, collect_splits({row["task_name"] for row in rows}))
    splits = json.loads(args.splits.read_text())
    cases, excluded = select_cases(rows, splits["tasks"])
    output = dict(schema_version=1, scope="cached MiniLM train/dev Top-1 feasibility only",
                  source_sha256=sha(CACHE / "rankings.jsonl"),
                  baseline_manifest_sha256=sha(CACHE / "summary.json"),
                  split_snapshot_sha256=sha(args.splits), code_sha256=sha(Path(__file__)),
                  cached_cases=len(rows), excluded=excluded, selected_cases=len(cases),
                  unique_task_ids=len({row["task_id"] for row in cases}),
                  agent_performance_measured=False, by_library=summarize(cases), cases=cases)
    write_new(args.output, output)
    print(json.dumps({key: value for key, value in output.items() if key != "cases"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
