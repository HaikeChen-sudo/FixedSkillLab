"""Deterministic local retrieval over the fixed ALFWorld Skill library."""

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import List

from alfworld_skills import AlfworldSkill, SKILL_LIST, render


EMBEDDER_NAME = "hash-embedding-v1"
BM25_RETRIEVER_NAME = "bm25-v1-body"
_WORD = re.compile(r"[a-z0-9_]+")
_TASK_GOAL = re.compile(r"Your task is to:\s*(.+)", re.IGNORECASE | re.DOTALL)


def routing_query(text: str) -> str:
    """Use the same goal-only query in online and offline retrieval."""
    match = _TASK_GOAL.search(text)
    return match.group(1).strip() if match else text.strip()


@dataclass(frozen=True)
class RetrievedSkill:
    name: str
    score: float
    rank: int


def skill_text(item: AlfworldSkill, body_aware: bool) -> str:
    return render(item) if body_aware else f"Name\n{item.name}\n\nDescription\n{item.description}\n"


def _tokens(text: str) -> List[str]:
    words = _WORD.findall(text.lower())
    return words + [f"{left}_{right}" for left, right in zip(words, words[1:])]


def retrieve_bm25(query: str, body_aware: bool = True, top_k: int = 3) -> List[RetrievedSkill]:
    documents = [_WORD.findall(skill_text(item, body_aware).lower()) for item in SKILL_LIST]
    lengths = [len(items) for items in documents]
    average_length = sum(lengths) / len(lengths)
    document_frequency = Counter(term for items in documents for term in set(items))
    scores = []
    for index, items in enumerate(documents):
        counts = Counter(items)
        score = 0.0
        for term in _WORD.findall(query.lower()):
            frequency = counts[term]
            if frequency:
                inverse_frequency = math.log(1 + (len(documents) - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
                score += inverse_frequency * frequency * 2.5 / (frequency + 1.5 * (0.25 + 0.75 * lengths[index] / average_length))
        scores.append((SKILL_LIST[index].name, score))
    scores.sort(key=lambda item: (-item[1], item[0]))
    return [RetrievedSkill(name, round(score, 6), rank) for rank, (name, score) in enumerate(scores[:top_k], 1)]


def _embedding(text: str, dimensions: int = 256) -> List[float]:
    values = [0.0] * dimensions
    for token in _tokens(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        values[int.from_bytes(digest[:4], "big") % dimensions] += 1 if digest[4] & 1 else -1
    return values


def _cosine(left: List[float], right: List[float]) -> float:
    norm = math.sqrt(sum(value * value for value in left) * sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / norm if norm else 0.0


def retrieve(query: str, body_aware: bool, top_k: int = 3) -> List[RetrievedSkill]:
    query_vector = _embedding(query)
    scored = [(item.name, _cosine(query_vector, _embedding(skill_text(item, body_aware)))) for item in SKILL_LIST]
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [RetrievedSkill(name, round(score, 6), rank) for rank, (name, score) in enumerate(scored[:top_k], 1)]
