"""Compare BM25 Body and Semantic Body Skill rankings task by task."""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


METHODS = ("bm25_body", "semantic_body")
LABELS = {
    (True, True): ("both_hit", "no_primary_top3_error"),
    (True, False): ("bm25_only", "semantic_ranking_error"),
    (False, True): ("semantic_only", "lexical_ranking_error"),
    (False, False): ("both_miss", "shared_retrieval_failure"),
}


def compare(rows):
    by_task = defaultdict(dict)
    for row in rows:
        if row["method"] in METHODS:
            by_task[row["task_id"]][row["method"]] = row
    result = []
    for task_id, methods in sorted(by_task.items()):
        if set(methods) != set(METHODS):
            raise ValueError(f"{task_id}: expected {', '.join(METHODS)}")
        bm25, semantic = (methods[name] for name in METHODS)
        bm25_hit = float(bm25["primary_hit_at_3"]) == 1
        semantic_hit = float(semantic["primary_hit_at_3"]) == 1
        category, diagnosis = LABELS[(bm25_hit, semantic_hit)]
        result.append({
            "task_id": task_id,
            "task_family": bm25["task_family"],
            "query": bm25["query"],
            "primary_gold": bm25["primary_gold"],
            "category": category,
            "diagnosis": diagnosis,
            "bm25_top_3": bm25["top_3"],
            "bm25_primary_rank": int(bm25["primary_rank"]),
            "semantic_top_3": semantic["top_3"],
            "semantic_primary_rank": int(semantic["primary_rank"]),
            "semantic_minus_bm25_rank": int(semantic["primary_rank"]) - int(bm25["primary_rank"]),
        })
    return result


def summarize(rows):
    family = defaultdict(Counter)
    for row in rows:
        family[row["task_family"]][row["category"]] += 1
    return {
        "tasks": len(rows),
        "categories": dict(Counter(row["category"] for row in rows)),
        "by_task_family": {name: dict(counts) for name, counts in sorted(family.items())},
        "bm25_primary_top3": sum(row["category"] in {"both_hit", "bm25_only"} for row in rows),
        "semantic_primary_top3": sum(row["category"] in {"both_hit", "semantic_only"} for row in rows),
        "tasks_requiring_review": [row["task_id"] for row in rows if row["category"] != "both_hit"],
    }


def main():
    parser = argparse.ArgumentParser(description="Compare BM25 and Semantic retrieval errors")
    parser.add_argument("details", type=Path)
    parser.add_argument("--output", type=Path, default=Path("results/retrieval_error_analysis.csv"))
    parser.add_argument("--summary", type=Path, default=Path("results/retrieval_error_summary.json"))
    args = parser.parse_args()
    with args.details.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    compared = compare(rows)
    fields = tuple(compared[0])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(compared)
    summary = summarize(compared)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
