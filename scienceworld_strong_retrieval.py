"""BM25 and frozen local MiniLM adapters for the existing ScienceWorld Agent."""

import json
import math
import subprocess
import sys
from pathlib import Path

from scienceworld_retrieval import skill_text
from scienceworld_retrieval_baselines import bm25_scores, digest, file_hash, local_encoder, ranked
from scienceworld_skills import library_hash, versioned_skills


ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / ".models/all-MiniLM-L6-v2"
RETRIEVAL_PYTHON = ROOT / ".venv/retrieval/bin/python"
BASELINE_MANIFEST = ROOT / "results/scienceworld_retrieval_baselines_2026-09-24/summary.json"
STRONG_CONDITIONS = {
    "bm25_flat_retrieval": ("bm25", False),
    "bm25_body_retrieval": ("bm25", True),
    "semantic_flat_retrieval": ("minilm", False),
    "semantic_body_retrieval": ("minilm", True),
}
RETRIEVERS = {"bm25": "scienceworld-bm25-v1", "minilm": "scienceworld-minilm-l6-v2-v1"}


def candidate_texts(query, body_aware, version):
    if not isinstance(query, str) or not query.strip():
        raise ValueError("strong retrieval requires the actual non-empty task description")
    if not isinstance(body_aware, bool):
        raise ValueError("body_aware must be a boolean")
    manifest = json.loads(BASELINE_MANIFEST.read_text(encoding="utf-8"))
    if version not in manifest["library_hashes"] or library_hash(version) != manifest["library_hashes"][version]:
        raise ValueError("Skill library differs from the frozen offline baseline")
    skills = versioned_skills(version)
    return [item.name for item in skills], [skill_text(item, body_aware) for item in skills], manifest


def minilm_scores(query, documents, model):
    texts = documents + [query]
    lengths = [len(model.tokenizer(text.strip(), add_special_tokens=True,
                                  truncation=False)["input_ids"]) for text in texts]
    # The baseline fit in 256 tokens. New oversized inputs must not silently change the indexed content.
    if any(length > model.max_seq_length for length in lengths):
        raise ValueError("MiniLM input exceeds its frozen token limit; no truncation fallback is allowed")
    vectors = model.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False)
    return [vector @ vectors[-1] for vector in vectors[:-1]], lengths


def local_result(query, body_aware, version, method):
    if method not in RETRIEVERS:
        raise ValueError(f"unsupported strong retriever: {method}")
    names, documents, manifest = candidate_texts(query, body_aware, version)
    metadata = {
        "adapter_version": "scienceworld-strong-retrieval-v1", "method": method,
        "retriever": RETRIEVERS[method], "index_mode": "body" if body_aware else "flat", "top_k": 3,
        "library_version": version, "library_sha256": library_hash(version),
        "query_sha256": digest(query.encode("utf-8")),
        "baseline_manifest_sha256": file_hash(BASELINE_MANIFEST),
        "indexed_text_sha256": {name: digest(text.encode("utf-8")) for name, text in zip(names, documents)},
    }
    if method == "bm25":
        scores = bm25_scores(query, documents)
        metadata["bm25"] = manifest["bm25"]
        metadata["execution"] = "in_process"
    else:
        model, model_metadata = local_encoder(MODEL_DIR)
        expected = manifest["minilm"]
        if any(model_metadata[key] != expected[key] for key in ("file_sha256", "packages", "dimension", "max_seq_length")):
            raise ValueError("local MiniLM files or dependencies differ from the frozen baseline")
        scores, lengths = minilm_scores(query, documents, model)
        metadata.update(model=model_metadata, execution="cold_local_worker_per_request",
                        query_tokens=lengths[-1], document_tokens=dict(zip(names, lengths[:-1])),
                        truncated=False)
    return {"hits": ranked(names, scores)[:3], "metadata": metadata}


def strong_retrieve(query, body_aware, version, method):
    if method == "bm25":
        return local_result(query, body_aware, version, method)
    if method != "minilm":
        raise ValueError(f"unsupported strong retriever: {method}")
    names, _, _ = candidate_texts(query, body_aware, version)
    if not RETRIEVAL_PYTHON.is_file():
        raise ValueError("missing .venv/retrieval/bin/python; no automatic installation or fallback")
    # ScienceWorld and torch live in separate existing environments; keep those dependencies isolated.
    request = dict(query=query, body_aware=body_aware, version=version)
    try:
        completed = subprocess.run(
            [str(RETRIEVAL_PYTHON), str(Path(__file__).resolve()), "--minilm-worker"],
            input=json.dumps(request), text=True, capture_output=True, timeout=120, cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("local MiniLM retrieval timed out; no fallback was used") from error
    if completed.returncode:
        raise RuntimeError("local MiniLM retrieval failed: " + completed.stderr[-2000:])
    try:
        result = json.loads(completed.stdout)
        hits, metadata = result["hits"], result["metadata"]
        if (len(hits) != 3 or len({hit["name"] for hit in hits}) != 3
                or any(hit["name"] not in names or hit["rank"] != index or not math.isfinite(hit["score"])
                       for index, hit in enumerate(hits, 1))
                or metadata["query_sha256"] != digest(query.encode("utf-8"))
                or metadata["library_sha256"] != library_hash(version)
                or metadata["index_mode"] != ("body" if body_aware else "flat")
                or metadata["retriever"] != RETRIEVERS[method]):
            raise ValueError("worker result does not match the requested retrieval")
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("invalid local MiniLM worker response; no fallback was used") from error
    return result


if __name__ == "__main__":
    if sys.argv[1:] != ["--minilm-worker"]:
        raise SystemExit("This local worker is called by scienceworld_agent.py; use the interface tests for offline checks.")
    payload = json.load(sys.stdin)
    print(json.dumps(local_result(payload["query"], payload["body_aware"], payload["version"], "minilm")))
