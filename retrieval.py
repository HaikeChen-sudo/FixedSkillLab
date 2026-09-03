"""Deterministic local embeddings for fixed-Skill retrieval experiments."""

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Iterable, List

from skills import SKILL_LIST, Skill, render


EMBEDDER_NAME = "hash-embedding-v1"
_WORD = re.compile(r"[a-z0-9_]+")


@dataclass(frozen=True)
class RetrievedSkill:
    name: str
    score: float
    rank: int


def skill_text(item: Skill, body_aware: bool) -> str:
    if body_aware:
        return render(item)
    return f"Name\n{item.name}\n\nDescription\n{item.description}\n"


def loaded_skill_text(names: Iterable[str]) -> str:
    by_name = {item.name: item for item in SKILL_LIST}
    return "\n---\n".join(render(by_name[name]) for name in names)


def _tokens(text: str) -> List[str]:
    words = _WORD.findall(text.lower())
    return words + [f"{left}_{right}" for left, right in zip(words, words[1:])]


def _embedding(text: str, dimensions: int = 256) -> List[float]:
    values = [0.0] * dimensions
    for token in _tokens(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        values[index] += 1 if digest[4] & 1 else -1
    return values


def _cosine(left: List[float], right: List[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def retrieve(query: str, body_aware: bool, top_k: int = 3) -> List[RetrievedSkill]:
    query_vector = _embedding(query)
    scored = [
        (item.name, _cosine(query_vector, _embedding(skill_text(item, body_aware))))
        for item in SKILL_LIST
    ]
    scored.sort(key=lambda pair: (-pair[1], pair[0]))
    return [RetrievedSkill(name, round(score, 6), rank) for rank, (name, score) in enumerate(scored[:top_k], 1)]
