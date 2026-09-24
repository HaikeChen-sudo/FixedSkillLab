"""Offline BM25 and local MiniLM controls on previously saved ScienceWorld queries.

The online router and historical Skill libraries are deliberately unchanged.
"""

import argparse
import hashlib
import json
import math
import os
import platform
from collections import Counter, defaultdict
from importlib.metadata import version as package_version
from pathlib import Path

from scienceworld_hash_audit import digest, load_cases, rank_skills
from scienceworld_retrieval import _WORD, skill_text
from scienceworld_skills import versioned_skills


METHODS = ("hash_256", "exact_counts", "bm25", "minilm")
MODEL_FILES = (
    "model.safetensors", "config.json", "config_sentence_transformers.json",
    "sentence_bert_config.json", "modules.json", "1_Pooling/config.json",
    "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "vocab.txt",
)


def ranked(names, scores):
    if len(names) != len(scores) or len(names) != len(set(names)):
        raise ValueError("scores must match distinct candidate names")
    pairs = [(name, float(score)) for name, score in zip(names, scores)]
    if any(not math.isfinite(score) for _, score in pairs):
        raise ValueError("non-finite retrieval score")
    pairs.sort(key=lambda pair: (-pair[1], pair[0]))
    return [{"name": name, "score": round(score, 6), "rank": rank}
            for rank, (name, score) in enumerate(pairs, 1)]


def bm25_scores(query, documents):
    """Keep the existing ALFWorld BM25 convention, including repeated query terms."""
    counts = [Counter(_WORD.findall(text.lower())) for text in documents]
    if not counts:
        raise ValueError("empty candidate library")
    lengths = [sum(row.values()) for row in counts]
    average_length = sum(lengths) / len(counts)
    if not average_length:
        return [0.0] * len(counts)
    df = Counter(term for row in counts for term in row)
    scores = []
    for row, length in zip(counts, lengths):
        score = 0.0
        for term in _WORD.findall(query.lower()):
            frequency = row[term]
            if frequency:
                idf = math.log(1 + (len(counts) - df[term] + 0.5) / (df[term] + 0.5))
                score += idf * frequency * 2.5 / (frequency + 1.5 * (0.25 + 0.75 * length / average_length))
        scores.append(score)
    return scores


def file_hash(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def local_encoder(model_dir):
    # Fail locally instead of silently downloading a different model revision.
    for name in MODEL_FILES:
        if not (model_dir / name).is_file():
            raise ValueError(f"missing local model file: {name}")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(2)
    torch.manual_seed(0)
    model = SentenceTransformer(str(model_dir.resolve()), device="cpu", local_files_only=True,
                                trust_remote_code=False, model_kwargs={"use_safetensors": True})
    model.eval()
    if model.max_seq_length != 256 or model.get_sentence_embedding_dimension() != 384:
        raise ValueError("expected the existing MiniLM 384-dimensional, 256-token configuration")
    metadata = {
        "local_directory_name": model_dir.name, "device": "cpu", "batch_size": 16,
        "dimension": 384, "max_seq_length": 256, "normalize_embeddings": True,
        "torch_threads": 2, "seed": 0, "use_safetensors": True,
        "file_sha256": {name: file_hash(model_dir / name) for name in MODEL_FILES},
        "python": platform.python_version(),
        "packages": {name: package_version(name) for name in (
            "sentence-transformers", "transformers", "torch", "numpy", "tokenizers", "safetensors",
        )},
    }
    return model, metadata


def compare(cases, model):
    libraries = {}
    inputs = []
    for version in sorted({case["library_version"] for case in cases}):
        for mode in ("flat", "body"):
            skills = versioned_skills(version)
            names = [item.name for item in skills]
            documents = [skill_text(item, mode == "body") for item in skills]
            libraries[(version, mode)] = (names, documents)
            inputs.extend(dict(kind="skill", library_version=version, mode=mode, name=name, text=text)
                          for name, text in zip(names, documents))
    queries = sorted({case["query"] for case in cases})
    inputs.extend(dict(kind="query", text=query) for query in queries)
    texts = sorted({row["text"] for row in inputs})
    vectors = model.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False)
    if not all(math.isfinite(float(value)) for row in vectors for value in row):
        raise ValueError("encoder produced non-finite values")
    encoded = dict(zip(texts, vectors))
    token_lengths = {text: len(model.tokenizer(text.strip(), add_special_tokens=True,
                                              truncation=False)["input_ids"]) for text in texts}
    for row in inputs:
        text = row.pop("text")
        row.update(text_sha256=digest(text.encode("utf-8")), tokens=token_lengths[text],
                   truncated=token_lengths[text] > model.max_seq_length)
    for case in cases:
        case["comparisons"] = {}
        for mode in ("flat", "body"):
            names, documents = libraries[(case["library_version"], mode)]
            rankings = {
                "hash_256": case["baseline"][mode],
                "exact_counts": rank_skills(case["query"], case["library_version"], mode == "body", None),
                "bm25": ranked(names, bm25_scores(case["query"], documents)),
                "minilm": ranked(names, [encoded[text] @ encoded[case["query"]] for text in documents]),
            }
            case["comparisons"][mode] = {}
            for method, ranks in rankings.items():
                gold = next(row for row in ranks if row["name"] == case["gold_skill"])
                case["comparisons"][mode][method] = {
                    "gold_rank": gold["rank"], "hit_at_3": gold["rank"] <= 3, "ranking": ranks,
                }
        del case["baseline"]
    return cases, inputs


def metrics(cases):
    if not cases:
        raise ValueError("cannot summarize an empty group")
    return [dict(mode=mode, method=method, cases=len(cases),
                 hit_at_1_count=sum(rank == 1 for rank in ranks),
                 hit_at_3_count=sum(rank <= 3 for rank in ranks),
                 hit_at_3=sum(rank <= 3 for rank in ranks) / len(ranks),
                 mrr=sum(1 / rank for rank in ranks) / len(ranks))
            for mode in ("flat", "body") for method in METHODS
            for ranks in [[case["comparisons"][mode][method]["gold_rank"] for case in cases]]]


def summarize(cases):
    libraries, runs, queries = defaultdict(list), defaultdict(list), defaultdict(dict)
    for case in cases:
        version = case["library_version"]
        libraries[version].append(case)
        queries[version][(case["query_sha256"], case["gold_skill"])] = case
        for run in {source["run_id"] for source in case["source_records"]}:
            runs[(run, version)].append(case)
    return {
        "by_library": [dict(library_version=version, **row)
                       for version, group in sorted(libraries.items()) for row in metrics(group)],
        "by_library_unique_query_gold": [dict(library_version=version, **row)
                                         for version, group in sorted(queries.items())
                                         for row in metrics(list(group.values()))],
        "by_run": [dict(run_id=run, library_version=version, **row)
                   for (run, version), group in sorted(runs.items()) for row in metrics(group)],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--model-dir", type=Path, default=Path(".models/all-MiniLM-L6-v2"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("output directory exists; choose a new directory to preserve saved results")
    cases, _, stats = load_cases(args.source)
    model, model_metadata = local_encoder(args.model_dir)
    cases, input_audit = compare(cases, model)
    summary = {
        "schema_version": 1, "scope": "retrospective offline retrieval controls; not Agent evaluation",
        "source": stats, "top_k": 3, "methods": list(METHODS),
        "unit": "task ID, library version/hash and exact query; repeats and conditions collapsed",
        "index_fields": {"flat": "Name and Description", "body": "complete rendered Skill"},
        "bm25": {"k1": 1.5, "b": 0.75, "idf": "log(1 + (N-df+0.5)/(df+0.5))",
                 "tokens": "lowercase regex words; repeated query terms counted; no stemming"},
        "minilm": model_metadata,
        "tie_break": "unrounded score descending, Skill name ascending",
        "library_hashes": {case["library_version"]: case["library_sha256"] for case in cases},
        "code_sha256": {name: file_hash(Path(__file__).with_name(name)) for name in (
            "scienceworld_retrieval_baselines.py", "scienceworld_hash_audit.py",
            "scienceworld_retrieval.py", "scienceworld_skills.py",
        )},
        "truncation": {kind: {"inputs": len(rows), "truncated": sum(row["truncated"] for row in rows),
                              "max_tokens": max(row["tokens"] for row in rows)}
                       for kind in ("query", "flat", "body")
                       for rows in [[row for row in input_audit if row.get("mode", row["kind"]) == kind]]},
        **summarize(cases),
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for name, rows in (("rankings.jsonl", cases), ("embedding_inputs.jsonl", input_audit)):
        content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
        (args.output_dir / name).write_text(content, encoding="utf-8")
        summary.setdefault("output_sha256", {})[name] = digest(content.encode("utf-8"))
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source": stats, "truncation": summary["truncation"],
                      "output_dir": str(args.output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
