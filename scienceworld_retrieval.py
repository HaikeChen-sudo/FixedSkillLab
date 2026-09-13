"""Deterministic local retrieval over the fixed ScienceWorld Skill library."""

import hashlib
import math
import re
from dataclasses import dataclass
from typing import List

from scienceworld_skills import ScienceWorldSkill, render, versioned_skills


EMBEDDER_NAME = "hash-embedding-v1"
_WORD = re.compile(r"[a-z0-9_]+")


@dataclass(frozen=True)
class RetrievedSkill:
    name: str
    score: float
    rank: int


def skill_text(item: ScienceWorldSkill, body_aware: bool) -> str:
    return render(item) if body_aware else f"Name\n{item.name}\n\nDescription\n{item.description}\n"


def _embedding(text: str, dimensions: int = 256) -> List[float]:
    values = [0.0] * dimensions
    words = _WORD.findall(text.lower())
    for token in words + [f"{left}_{right}" for left, right in zip(words, words[1:])]:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        values[int.from_bytes(digest[:4], "big") % dimensions] += 1 if digest[4] & 1 else -1
    return values


def _cosine(left: List[float], right: List[float]) -> float:
    norm = math.sqrt(sum(value * value for value in left) * sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / norm if norm else 0.0


def retrieve(query: str, body_aware: bool, top_k: int = 3, version: str = "v3") -> List[RetrievedSkill]:
    skills = versioned_skills(version)
    query_vector = _embedding(query)
    scored = [(item.name, _cosine(query_vector, _embedding(skill_text(item, body_aware)))) for item in skills]
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [RetrievedSkill(name, round(score, 6), rank) for rank, (name, score) in enumerate(scored[:top_k], 1)]
