"""Replay saved retrievals and compare hashing with uncompressed term counts.

This diagnostic never imports the Agent, starts Java, or calls a model.
"""

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from scienceworld_retrieval import EMBEDDER_NAME, _WORD, _cosine, _embedding, skill_text
from scienceworld_skills import library_hash, versioned_skills


DIMENSIONS = (256, 1024, 4096, 65536)
METHODS = tuple(f"hash_{dimension}" for dimension in DIMENSIONS) + ("exact_counts",)
SOURCE_FIELDS = (
    "run_id", "task_id", "task_name", "suite", "variation_split", "condition", "repeat",
    "retriever", "retrieval_query", "skill_library_version", "skill_library_sha256",
    "gold_skills", "gold_skill_ranks", "skills_loaded", "retrieval",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def term_counts(text):
    words = _WORD.findall(text.lower())
    return Counter(words + [f"{left}_{right}" for left, right in zip(words, words[1:])])


def count_cosine(left, right):
    norm = math.sqrt(sum(v * v for v in left.values()) * sum(v * v for v in right.values()))
    return sum(value * right.get(term, 0) for term, value in left.items()) / norm if norm else 0.0


def rank_skills(query, version, body, dimensions):
    vector = term_counts if dimensions is None else lambda text: _embedding(text, dimensions)
    cosine = count_cosine if dimensions is None else _cosine
    query_vector = vector(query)
    scores = [(item.name, cosine(query_vector, vector(skill_text(item, body))))
              for item in versioned_skills(version)]
    scores.sort(key=lambda pair: (-pair[1], pair[0]))
    return [{"name": name, "score": round(score, 6), "rank": rank}
            for rank, (name, score) in enumerate(scores, 1)]


def load_cases(path):
    cases, sources = {}, []
    skipped = Counter()
    source_bytes = path.read_bytes()
    for line_number, line in enumerate(source_bytes.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("retriever") != EMBEDDER_NAME:
            skipped["not_hash_retrieval"] += 1
            continue
        version = row.get("skill_library_version")
        if row.get("skill_library_sha256") != library_hash(version):
            raise ValueError(f"line {line_number}: Skill library hash mismatch for {version}")
        query, gold = row.get("retrieval_query"), row.get("gold_skills")
        names = {item.name for item in versioned_skills(version)}
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"line {line_number}: missing query")
        if not isinstance(gold, list) or len(gold) != 1 or gold[0] not in names:
            raise ValueError(f"line {line_number}: expected one valid Gold label")
        condition = row.get("condition", "")
        if not condition.startswith(("flat_retrieval", "body_")):
            raise ValueError(f"line {line_number}: unsupported hash condition {condition}")
        if not row.get("task_id") or not row.get("run_id"):
            raise ValueError(f"line {line_number}: missing task or run identity")
        query_hash = digest(query.encode("utf-8"))
        key = (row["task_id"], version, query_hash)
        if key not in cases:
            cases[key] = {
                "task_id": row["task_id"], "task_name": row["task_name"],
                "query": query, "query_sha256": query_hash,
                "library_version": version, "library_sha256": row["skill_library_sha256"],
                "gold_skill": gold[0], "source_records": [],
                "baseline": {mode: rank_skills(query, version, mode == "body", 256)
                             for mode in ("flat", "body")},
            }
        case = cases[key]
        if case["gold_skill"] != gold[0]:
            raise ValueError(f"line {line_number}: conflicting Gold labels for the same query")
        mode = "flat" if condition.startswith("flat_retrieval") else "body"
        expected = case["baseline"][mode][:3]
        if row.get("retrieval") != expected or row.get("skills_loaded") != [hit["name"] for hit in expected]:
            raise ValueError(f"line {line_number}: saved Top-3 does not match hash-256 replay")
        expected_rank = next((hit["rank"] for hit in expected if hit["name"] == gold[0]), None)
        if row.get("gold_skill_ranks") != [expected_rank]:
            raise ValueError(f"line {line_number}: saved Gold rank does not match replay")
        source = {field: row.get(field) for field in SOURCE_FIELDS}
        source.update(source_file=row.get("source_file", path.name),
                      source_line=row.get("source_line", line_number))
        sources.append(source)
        case["source_records"].append({field: source[field] for field in (
            "source_file", "source_line", "run_id", "condition", "repeat", "suite", "variation_split",
        )})
    if not cases:
        raise ValueError("no saved hash retrievals found; no report was written")
    stats = {
        "input_file": path.name, "input_sha256": digest(source_bytes),
        "records_read": len(sources) + sum(skipped.values()), "selected_records": len(sources),
        "excluded_records": dict(skipped), "replayed_matching_records": len(sources),
        "unique_task_library_queries": len(cases),
        "duplicate_measurements_collapsed": len(sources) - len(cases),
    }
    return [cases[key] for key in sorted(cases)], sources, stats


def compare_cases(cases):
    for case in cases:
        comparisons = {}
        for mode in ("flat", "body"):
            comparisons[mode] = {}
            for dimensions in DIMENSIONS + (None,):
                method = f"hash_{dimensions}" if dimensions else "exact_counts"
                ranks = (case["baseline"][mode] if dimensions == 256 else
                         rank_skills(case["query"], case["library_version"], mode == "body", dimensions))
                gold = next(hit for hit in ranks if hit["name"] == case["gold_skill"])
                comparisons[mode][method] = {
                    "gold_rank": gold["rank"], "gold_score": gold["score"],
                    "hit_at_3": gold["rank"] <= 3, "top_3": ranks[:3],
                }
        case["comparisons"] = comparisons
        del case["baseline"]
    return cases


def group_metrics(cases):
    rows = []
    for mode in ("flat", "body"):
        for method in METHODS:
            ranks = [case["comparisons"][mode][method]["gold_rank"] for case in cases]
            rows.append({
                "mode": mode, "method": method, "cases": len(cases),
                "hit_at_1_count": sum(rank == 1 for rank in ranks),
                "hit_at_3_count": sum(rank <= 3 for rank in ranks),
                "hit_at_3": sum(rank <= 3 for rank in ranks) / len(cases),
                "mrr": sum(1 / rank for rank in ranks) / len(cases),
            })
    return rows


def summarize(cases):
    versions, runs = defaultdict(list), defaultdict(list)
    for case in cases:
        versions[case["library_version"]].append(case)
        for run in sorted({source["run_id"] for source in case["source_records"]}):
            runs[(run, case["library_version"])].append(case)
    version_rows, transitions = [], []
    for version, group in sorted(versions.items()):
        version_rows.extend(dict(library_version=version, **row) for row in group_metrics(group))
        for mode in ("flat", "body"):
            counts = Counter()
            changed = []
            for case in group:
                hashed = case["comparisons"][mode]["hash_256"]
                exact = case["comparisons"][mode]["exact_counts"]
                state = ("both_hit" if hashed["hit_at_3"] else "recovered_without_hashing") if exact["hit_at_3"] else (
                    "lost_without_hashing" if hashed["hit_at_3"] else "both_miss")
                counts[state] += 1
                if hashed["hit_at_3"] != exact["hit_at_3"]:
                    changed.append({"task_id": case["task_id"], "query_sha256": case["query_sha256"],
                                    "hash_256_rank": hashed["gold_rank"], "exact_rank": exact["gold_rank"],
                                    "change": state})
            transitions.append({"library_version": version, "mode": mode, "cases": len(group),
                                "counts": dict(counts), "changed_cases": changed})
    return {
        "by_library": version_rows,
        "by_run": [dict(run_id=run, library_version=version, **row)
                   for (run, version), group in sorted(runs.items()) for row in group_metrics(group)],
        "hash_256_to_exact": transitions,
        "query_coverage": [{"library_version": version, "task_library_queries": len(group),
                            "unique_task_ids": len({case["task_id"] for case in group}),
                            "unique_query_texts": len({case["query_sha256"] for case in group}),
                            "skill_count": len(versioned_skills(version))}
                           for version, group in sorted(versions.items())],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="episode JSONL or this audit's source_records.jsonl")
    parser.add_argument("--output-dir", type=Path, required=True, help="new directory; existing data is never overwritten")
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("output directory already exists; choose a new directory")
    cases, sources, stats = load_cases(args.source)
    cases = compare_cases(cases)
    summary = {
        "schema_version": 1, "scope": "retrospective offline sensitivity analysis of saved hash retrievals",
        "source": stats, "hash_dimensions": list(DIMENSIONS), "top_k": 3,
        "unit": "one task ID, Skill library version/hash and exact query text; repeats and conditions collapsed",
        "features": "existing lowercase regex words plus adjacent word pairs; no stemming or learned embeddings",
        "tie_break": "unrounded cosine descending, Skill name ascending",
        "library_hashes": {case["library_version"]: case["library_sha256"] for case in cases},
        "code_sha256": {name: digest(Path(__file__).with_name(name).read_bytes()) for name in (
            "scienceworld_hash_audit.py", "scienceworld_retrieval.py", "scienceworld_skills.py",
        )},
        **summarize(cases),
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for filename, rows in (("source_records.jsonl", sources), ("rankings.jsonl", cases)):
        output = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
        (args.output_dir / filename).write_text(output, encoding="utf-8")
        summary.setdefault("output_sha256", {})[filename] = digest(output.encode("utf-8"))
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({**stats, "output_dir": str(args.output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
