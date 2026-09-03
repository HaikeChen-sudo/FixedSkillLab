"""Evaluate fixed-Skill retrieval without running an LLM or ALFWorld episode."""

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean

from alfworld_retrieval import retrieve, retrieve_bm25, skill_text
from alfworld_skills import SKILL_LIST, library_hash
from result_utils import deduplicate_records


def task_query(game_file):
    import re

    grammar = json.loads(Path(game_file).read_text(encoding="utf-8"))["grammar"]
    match = re.search(r'"task"\s*:\s*\[\s*\{\s*"rhs"\s*:\s*"([^"]+)"', grammar)
    if not match:
        raise ValueError(f"task text not found in {game_file}")
    return match.group(1)


def tfidf_rank(query, documents):
    from sklearn.feature_extraction.text import TfidfVectorizer

    matrix = TfidfVectorizer(ngram_range=(1, 2), lowercase=True).fit_transform(documents + [query])
    scores = (matrix[:-1] @ matrix[-1].T).toarray().ravel()
    return sorted(range(len(documents)), key=lambda index: (-scores[index], SKILL_LIST[index].name))


def semantic_ranker(model, documents):
    document_vectors = model.encode(documents, normalize_embeddings=True, show_progress_bar=False)
    model.encode("warmup", normalize_embeddings=True, show_progress_bar=False)

    def rank(query):
        query_vector = model.encode(query, normalize_embeddings=True, show_progress_bar=False)
        scores = document_vectors @ query_vector
        return [SKILL_LIST[index].name for index in sorted(range(len(documents)), key=lambda index: (-scores[index], SKILL_LIST[index].name))]

    return rank


def rank_metrics(ranked_names, gold_names):
    ranks = {name: index for index, name in enumerate(ranked_names, 1)}
    gold_ranks = [ranks[name] for name in gold_names]
    primary_rank = ranks[gold_names[1]]
    return {
        "recall_at_1": sum(rank <= 1 for rank in gold_ranks) / len(gold_ranks),
        "recall_at_3": sum(rank <= 3 for rank in gold_ranks) / len(gold_ranks),
        "hit_at_1": float(min(gold_ranks) <= 1),
        "hit_at_3": float(min(gold_ranks) <= 3),
        "all_gold_at_3": float(max(gold_ranks) <= 3),
        "mrr": 1 / min(gold_ranks),
        "primary_gold": gold_names[1],
        "primary_rank": primary_rank,
        "primary_hit_at_1": float(primary_rank <= 1),
        "primary_hit_at_3": float(primary_rank <= 3),
        "primary_mrr": 1 / primary_rank,
        "gold_ranks": gold_ranks,
    }


def load_tasks(results, run_id):
    records = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = [row for row in records if row.get("run_id") == run_id]
    records, _ = deduplicate_records(records)
    tasks = {}
    for row in records:
        tasks.setdefault(row["task_index"], {
            "task_id": row["task_id"],
            "task_index": row["task_index"],
            "task_family": row.get("task_family") or "unknown",
            "query": task_query(row["game_file"]),
            "gold_skills": row["gold_skills"],
        })
    return [tasks[index] for index in sorted(tasks)]


def evaluate(tasks, embedding_model=None, selected_methods=None):
    methods = {}
    for body_aware in (False, True):
        suffix = "body" if body_aware else "flat"
        documents = [skill_text(item, body_aware) for item in SKILL_LIST]
        methods[f"hash_{suffix}"] = lambda query, aware=body_aware: [item.name for item in retrieve(query, aware, len(SKILL_LIST))]
        methods[f"bm25_{suffix}"] = lambda query, aware=body_aware: [item.name for item in retrieve_bm25(query, aware, len(SKILL_LIST))]
        methods[f"tfidf_{suffix}"] = lambda query, docs=documents: [SKILL_LIST[index].name for index in tfidf_rank(query, docs)]
        if embedding_model is not None:
            methods[f"semantic_{suffix}"] = semantic_ranker(embedding_model, documents)

    if selected_methods:
        unknown = set(selected_methods) - set(methods)
        if unknown:
            raise ValueError(f"unknown retrieval methods: {', '.join(sorted(unknown))}")
        methods = {name: methods[name] for name in selected_methods}

    details = []
    for method, ranker in methods.items():
        for task in tasks:
            started = time.perf_counter()
            ranked = ranker(task["query"])
            metrics = rank_metrics(ranked, task["gold_skills"])
            details.append({
                "method": method,
                **task,
                **metrics,
                "latency_ms": (time.perf_counter() - started) * 1000,
                "top_3": ranked[:3],
            })
    return details


def aggregate(rows):
    metric_names = ("recall_at_1", "recall_at_3", "hit_at_1", "hit_at_3", "all_gold_at_3", "mrr", "primary_hit_at_1", "primary_hit_at_3", "primary_mrr", "latency_ms")
    groups = defaultdict(list)
    family_groups = defaultdict(list)
    for row in rows:
        groups[row["method"]].append(row)
        family_groups[(row["method"], row["task_family"])].append(row)
    overall = [{"method": method, "tasks": len(items), **{name: mean(row[name] for row in items) for name in metric_names}} for method, items in sorted(groups.items())]
    by_family = [{"method": method, "task_family": family, "tasks": len(items), **{name: mean(row[name] for row in items) for name in metric_names}} for (method, family), items in sorted(family_groups.items())]
    return overall, by_family


def main():
    parser = argparse.ArgumentParser(description="Offline ALFWorld Skill retrieval benchmark")
    parser.add_argument("results", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--summary", type=Path, default=Path("results/retrieval_benchmark_summary.json"))
    parser.add_argument("--details", type=Path, default=Path("results/retrieval_benchmark_details.csv"))
    parser.add_argument("--embedding-model", type=Path, help="local SentenceTransformer model directory")
    parser.add_argument("--methods", help="Comma-separated methods; default evaluates every available method")
    args = parser.parse_args()

    tasks = load_tasks(args.results, args.run_id)
    if len(tasks) != 30:
        parser.error(f"expected 30 unique tasks, found {len(tasks)}")
    embedding_model = None
    if args.embedding_model:
        from sentence_transformers import SentenceTransformer

        embedding_model = SentenceTransformer(str(args.embedding_model), local_files_only=True)
    selected_methods = args.methods.split(",") if args.methods else None
    details = evaluate(tasks, embedding_model, selected_methods)
    overall, by_family = aggregate(details)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps({
        "run_id": args.run_id,
        "query_source": "game.tw-pddl grammar task",
        "tasks": len(tasks),
        "skills": len(SKILL_LIST),
        "skill_library_sha256": library_hash(),
        "embedding_model": str(args.embedding_model) if args.embedding_model else None,
        "overall": overall,
        "by_task_family": by_family,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    args.details.parent.mkdir(parents=True, exist_ok=True)
    fields = ("method", "task_id", "task_index", "task_family", "query", "gold_skills", "primary_gold", "top_3", "gold_ranks", "primary_rank", "recall_at_1", "recall_at_3", "hit_at_1", "hit_at_3", "all_gold_at_3", "mrr", "primary_hit_at_1", "primary_hit_at_3", "primary_mrr", "latency_ms")
    with args.details.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in details:
            writer.writerow({name: json.dumps(row[name], ensure_ascii=False) if isinstance(row[name], list) else row[name] for name in fields})
    for row in overall:
        print(json.dumps(row, ensure_ascii=False))
    print(json.dumps({"summary": str(args.summary), "details": str(args.details)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
