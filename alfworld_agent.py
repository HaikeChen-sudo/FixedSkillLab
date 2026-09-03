"""Run one text-only ALFWorld episode under a fixed-Skill condition."""

import argparse
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent import DeepSeekChatClient
from alfworld_gold_skills import gold_skills_for_game
from alfworld_retrieval import BM25_RETRIEVER_NAME, EMBEDDER_NAME, retrieve, retrieve_bm25, routing_query
from alfworld_skills import SKILL_LIST, library_hash, loaded_skill_text
from alfworld.agents.environment import get_environment


ACT_TOOL = {
    "type": "function",
    "function": {
        "name": "act",
        "description": "Send exactly one text command to the ALFWorld environment.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
            "additionalProperties": False,
        },
    },
}

SYSTEM_PROMPT = """You control a text-based household environment.
Reach the task goal by calling act with exactly one action at a time. Read each new observation before acting again.

Use ALFWorld command grammar exactly:
- go to <location>
- open <receptacle> / close <receptacle>
- take <object> from <receptacle>
- move <object> to <receptacle>
- heat <object> with <microwave>
- cool <object> with <fridge>
- clean <object> with <sinkbasin>
- use <desklamp> / examine <object>

For a light-inspection goal, hold the target object and call use <desklamp>; this completes the inspection. Never use put, place, drop, throw, find, look around, or toggle. If the environment says "Nothing happens.", the prior action failed: inspect the latest state and issue a different valid command. Do not repeat it.
Do not claim success yourself. The environment decides success. Do not use any tools other than act."""

PRICING_PER_MILLION = {
    "deepseek-v4-flash": {"cache_hit": 0.0028, "cache_miss": 0.14, "output": 0.28},
    "deepseek-v4-pro": {"cache_hit": 0.003625, "cache_miss": 0.435, "output": 0.87},
}
CONDITIONS = ("no_skill", "all_skills", "flat_retrieval", "body_aware_retrieval", "bm25_body_retrieval", "oracle_skill")
AGENT_PROTOCOL_VERSION = "v5-goal-only-router"

@dataclass(frozen=True)
class SkillSelection:
    names: List[str]
    retrieved: List[Dict[str, Any]]
    gold_skill_ranks: List[Optional[int]]
    retriever: Optional[str]
    gold_skills: List[str]


def select_skills(condition: str, task_text: str, game_file: str) -> SkillSelection:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    gold = list(gold_skills_for_game(game_file))
    if condition == "no_skill":
        return SkillSelection([], [], [], None, gold)
    if condition == "all_skills":
        return SkillSelection([item.name for item in SKILL_LIST], [], [], None, gold)
    if condition == "oracle_skill":
        return SkillSelection(gold, [], [], None, gold)
    if condition == "bm25_body_retrieval":
        hits = retrieve_bm25(task_text)
        retriever = BM25_RETRIEVER_NAME
    else:
        hits = retrieve(task_text, body_aware=condition == "body_aware_retrieval")
        retriever = EMBEDDER_NAME
    ranks = {item.name: item.rank for item in hits}
    return SkillSelection(
        [item.name for item in hits],
        [asdict(item) for item in hits],
        [ranks.get(name) for name in gold],
        retriever,
        gold,
    )


def action_result(observation: List[str], scores: List[float], dones: List[bool], infos: Dict[str, Any]) -> Dict[str, Any]:
    text = observation[0]
    rejected = text.strip() == "Nothing happens."
    result = {
        "ok": not rejected,
        "observation": text,
        "score": scores[0],
        "done": bool(dones[0]),
        "won": bool(infos["won"][0]),
    }
    if rejected:
        result["error"] = "The environment rejected or could not apply this action. Use a different valid command."
    return result


def environment_config(data_dir: Path, split: str, max_steps: int) -> Dict[str, Any]:
    data_path = data_dir / "json_2.1.1" / split
    if not data_path.is_dir():
        raise FileNotFoundError(f"ALFWorld task data is missing: {data_path}")
    return {
        "env": {
            "type": "AlfredTWEnv",
            "goal_desc_human_anns_prob": 0,
            "task_types": [1, 2, 3, 4, 5, 6],
            "domain_randomization": False,
            "expert_type": "handcoded",
        },
        "dataset": {"eval_ood_data_path": str(data_path), "num_eval_games": 0},
        "general": {"training_method": "dagger"},
        "dagger": {"training": {"max_nb_steps_per_episode": max_steps}},
    }


def make_env(data_dir: Path, split: str, max_steps: int, task_index: int, expert: bool = False):
    config = environment_config(data_dir, split, max_steps)
    train_eval = "train" if expert else "eval_out_of_distribution"
    if expert:
        config["dataset"]["data_path"] = config["dataset"]["eval_ood_data_path"]
        config["dataset"]["num_train_games"] = 0
    source = get_environment("AlfredTWEnv")(config, train_eval=train_eval)
    if not 0 <= task_index < len(source.game_files):
        raise ValueError(f"--task-index must be between 0 and {len(source.game_files) - 1}")
    game_file = source.game_files[task_index]
    source.game_files = [game_file]
    source.num_games = 1
    return source.init_env(1), game_file


def run_expert_check(data_dir: Path, split: str, max_steps: int, task_index: int) -> Dict[str, Any]:
    env, game_file = make_env(data_dir, split, max_steps, task_index, expert=True)
    trace: List[str] = []
    try:
        _, infos = env.reset()
        done = False
        won = False
        score = 0
        while len(trace) < max_steps and not done:
            command = infos["extra.expert_plan"][0][0]
            trace.append(command)
            _, scores, dones, infos = env.step([command])
            score = scores[0]
            done = bool(dones[0])
            won = bool(infos["won"][0])
        return {
            "environment": "alfworld_text",
            "condition": "expert_control",
            "agent_protocol_version": AGENT_PROTOCOL_VERSION,
            "task_id": f"{split}:{task_index:03d}",
            "game_file": game_file,
            "success": won,
            "done": done,
            "score": score,
            "steps": len(trace),
            "trace": trace,
        }
    finally:
        env.close()


def run_episode(
    model: str,
    temperature: float,
    data_dir: Path,
    split: str,
    max_steps: int,
    task_index: int,
    condition: str = "no_skill",
) -> Dict[str, Any]:
    env, game_file = make_env(data_dir, split, max_steps, task_index)
    started = time.perf_counter()
    trace: List[Dict[str, Any]] = []
    try:
        observation, _ = env.reset()
        retrieval_query = routing_query(observation[0])
        selection = select_skills(condition, retrieval_query, game_file)
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        if selection.names:
            messages.append({"role": "system", "content": "Fixed Skill guidance:\n" + loaded_skill_text(selection.names)})
        messages.append({"role": "user", "content": "Observation:\n" + observation[0]})
        client = DeepSeekChatClient(model, temperature, tools=[ACT_TOOL])
        won = False
        done = False
        final_text = ""
        llm_calls = 0

        while len(trace) < max_steps and not done:
            reply = client.respond(messages)
            llm_calls += 1
            messages.append(reply)
            calls = reply.get("tool_calls") or []
            if not calls:
                final_text = reply.get("content") or ""
                break
            call = calls[0]
            try:
                command = json.loads(call["function"]["arguments"])["command"]
                if call.get("function", {}).get("name") != "act" or not isinstance(command, str):
                    raise ValueError("the only available tool is act(command)")
                observation, scores, dones, infos = env.step([command])
                result = action_result(observation, scores, dones, infos)
                done = result["done"]
                won = result["won"]
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                command = ""
                result = {"ok": False, "error": str(error)}
            trace.append({"tool": "act", "command": command, "result": result})
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id", "missing-call-id"),
                "content": json.dumps(result, ensure_ascii=False),
            })
        metrics = client.metrics()
        price = PRICING_PER_MILLION.get(model)
        cost_usd = None if price is None else (
            metrics["prompt_cache_hit_tokens"] * price["cache_hit"]
            + metrics["prompt_cache_miss_tokens"] * price["cache_miss"]
            + metrics["output_tokens"] * price["output"]
        ) / 1_000_000
        return {
            "environment": "alfworld_text",
            "task_id": f"{split}:{task_index:03d}",
            "task_index": task_index,
            "game_file": game_file,
            "condition": condition,
            "agent_protocol_version": AGENT_PROTOCOL_VERSION,
            "model": model,
            "temperature": temperature,
            "success": won,
            "done": done,
            "steps": len(trace),
            "llm_calls": llm_calls,
            "tool_calls": len(trace),
            "input_tokens": metrics["input_tokens"],
            "output_tokens": metrics["output_tokens"],
            "total_tokens": metrics["input_tokens"] + metrics["output_tokens"],
            "prompt_cache_hit_tokens": metrics["prompt_cache_hit_tokens"],
            "prompt_cache_miss_tokens": metrics["prompt_cache_miss_tokens"],
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "cost_usd": cost_usd,
            "skills_loaded": selection.names,
            "gold_skills": selection.gold_skills,
            "retriever": selection.retriever,
            "retrieval_query": retrieval_query,
            "retrieval": selection.retrieved,
            "gold_skill_ranks": selection.gold_skill_ranks,
            "retrieval_rank": min((rank for rank in selection.gold_skill_ranks if rank is not None), default=None),
            "primary_gold_skill_rank": selection.gold_skill_ranks[1] if len(selection.gold_skill_ranks) > 1 else None,
            "skill_library_sha256": library_hash(),
            "final_text": final_text,
            "trace": trace,
        }
    finally:
        env.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one text-only ALFWorld fixed-Skill episode")
    parser.add_argument("--model", help="DeepSeek model ID; required unless --smoke is used")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--data-dir", type=Path, default=Path(".alfworld-data"))
    parser.add_argument("--split", default="valid_unseen", choices=("valid_seen", "valid_unseen"))
    parser.add_argument("--task-index", type=int, default=0, help="zero-based task index within the selected split")
    parser.add_argument("--condition", choices=CONDITIONS, default="no_skill")
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--results", type=Path, default=Path("results/alfworld_results.jsonl"))
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--smoke", action="store_true", help="reset one task and take a local look action; no API call")
    parser.add_argument("--expert-check", action="store_true", help="run ALFWorld's local expert; no API call")
    args = parser.parse_args()
    if args.max_steps < 1:
        parser.error("--max-steps must be positive")
    if args.smoke:
        env, _ = make_env(args.data_dir, args.split, args.max_steps, args.task_index)
        try:
            observation, _ = env.reset()
            observation, scores, dones, infos = env.step(["look"])
            print(json.dumps({"success": bool(infos["won"][0]), "done": bool(dones[0]), "score": scores[0], "observation": observation[0]}, ensure_ascii=False, indent=2))
        finally:
            env.close()
        return 0
    if args.expert_check:
        print(json.dumps(run_expert_check(args.data_dir, args.split, args.max_steps, args.task_index), ensure_ascii=False, indent=2))
        return 0
    if not args.model:
        parser.error("--model is required unless --smoke is used")
    record = run_episode(args.model, args.temperature, args.data_dir, args.split, args.max_steps, args.task_index, args.condition)
    record.update({"run_id": args.run_id, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "split": args.split})
    args.results.parent.mkdir(parents=True, exist_ok=True)
    with args.results.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
