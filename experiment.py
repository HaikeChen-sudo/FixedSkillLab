"""Run frozen A–E Mini Lab experiments and append one JSON record per episode."""

import argparse
import hashlib
import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agent import Agent, DeepSeekChatClient
from gold_skills import GOLD_SKILLS
from retrieval import EMBEDDER_NAME, loaded_skill_text, retrieve
from skills import SKILL_LIST, render
from tasks import TASKS, V4_TASK_IDS


CONDITIONS = ("no_skill", "all_skills", "flat_retrieval", "body_aware_retrieval", "oracle_skill")
PRICING_PER_MILLION = {
    "deepseek-v4-flash": {"cache_hit": 0.0028, "cache_miss": 0.14, "output": 0.28},
    "deepseek-v4-pro": {"cache_hit": 0.003625, "cache_miss": 0.435, "output": 0.87},
}


@dataclass(frozen=True)
class SkillSelection:
    names: List[str]
    retrieved: List[Dict[str, Any]]
    gold_skill_ranks: List[Optional[int]]
    retriever: Optional[str]


def select_skills(task_id: str, condition: str) -> SkillSelection:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    gold = GOLD_SKILLS[task_id]
    if condition == "no_skill":
        return SkillSelection([], [], [], None)
    if condition == "all_skills":
        return SkillSelection([item.name for item in SKILL_LIST], [], [], None)
    if condition == "oracle_skill":
        return SkillSelection(list(gold), [], [], None)
    hits = retrieve(TASKS[task_id].instruction, body_aware=condition == "body_aware_retrieval")
    names = [item.name for item in hits]
    ranks = {item.name: item.rank for item in hits}
    return SkillSelection(
        names,
        [asdict(item) for item in hits],
        [ranks.get(name) for name in gold],
        EMBEDDER_NAME,
    )


def skill_library_hash() -> str:
    text = "\n".join(render(item) for item in SKILL_LIST)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cost_usd(model: str, episode: Any) -> Optional[float]:
    price = PRICING_PER_MILLION.get(model)
    if not price:
        return None
    return (
        episode.prompt_cache_hit_tokens * price["cache_hit"]
        + episode.prompt_cache_miss_tokens * price["cache_miss"]
        + episode.output_tokens * price["output"]
    ) / 1_000_000


def run_episode(
    task_id: str,
    condition: str,
    model: str,
    temperature: float,
    repeat: int,
    run_id: str,
    client_factory: Callable[[], Any],
) -> Dict[str, Any]:
    selection = select_skills(task_id, condition)
    episode = Agent(client_factory()).run(task_id, loaded_skill_text(selection.names))
    gold_ranks = selection.gold_skill_ranks
    found_ranks = [rank for rank in gold_ranks if rank is not None]
    return {
        "schema_version": 1,
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
        "condition": condition,
        "repeat": repeat,
        "model": model,
        "temperature": temperature,
        "thinking": "disabled",
        "success": episode.success,
        "input_tokens": episode.input_tokens,
        "output_tokens": episode.output_tokens,
        "total_tokens": episode.input_tokens + episode.output_tokens,
        "prompt_cache_hit_tokens": episode.prompt_cache_hit_tokens,
        "prompt_cache_miss_tokens": episode.prompt_cache_miss_tokens,
        "llm_calls": episode.llm_calls,
        "tool_calls": episode.tool_calls,
        "steps": episode.steps,
        "latency_ms": episode.latency_ms,
        "cost_usd": cost_usd(model, episode),
        "skills_loaded": selection.names,
        "gold_skills": list(GOLD_SKILLS[task_id]),
        "retriever": selection.retriever,
        "retrieval": selection.retrieved,
        "gold_skill_ranks": gold_ranks,
        "retrieval_rank": min(found_ranks) if found_ranks else None,
        "final_text": episode.final_text,
        "trace": episode.trace,
        "skill_library_sha256": skill_library_hash(),
    }


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _conditions(value: str) -> List[str]:
    names = value.split(",")
    unknown = sorted(set(names) - set(CONDITIONS))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown conditions: {', '.join(unknown)}")
    return names


def _task_ids(value: str) -> List[str]:
    names = value.split(",")
    unknown = sorted(set(names) - set(TASKS))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown tasks: {', '.join(unknown)}")
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description="Run A–E fixed-Skill experiments with DeepSeek")
    parser.add_argument("--model", required=True)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--conditions", type=_conditions, default=list(CONDITIONS))
    tasks = parser.add_mutually_exclusive_group(required=True)
    tasks.add_argument("--tasks", type=_task_ids, help="comma-separated task IDs")
    tasks.add_argument("--all-tasks", action="store_true", help="run every task; this sends many API requests")
    tasks.add_argument("--suite", choices=("v4",), help="run the frozen 30-task v4 benchmark")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--results", type=Path, default=Path("results/results.jsonl"))
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--order-seed", type=int, default=0)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    task_ids = sorted(TASKS) if args.all_tasks else V4_TASK_IDS if args.suite == "v4" else args.tasks
    for task_id in task_ids:
        for repeat in range(args.repeats):
            conditions = list(args.conditions)
            random.Random(f"{args.order_seed}:{task_id}:{repeat}").shuffle(conditions)
            for condition in conditions:
                started = time.perf_counter()
                record = run_episode(
                    task_id, condition, args.model, args.temperature, repeat, args.run_id,
                    lambda: DeepSeekChatClient(args.model, args.temperature),
                )
                append_jsonl(args.results, record)
                print(json.dumps({
                    "run_id": args.run_id,
                    "task_id": task_id,
                    "condition": condition,
                    "success": record["success"],
                    "latency_ms": record["latency_ms"],
                    "runner_ms": round((time.perf_counter() - started) * 1000),
                }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
