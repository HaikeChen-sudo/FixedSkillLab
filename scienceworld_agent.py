"""Run one objectively scored ScienceWorld episode with DeepSeek."""

import argparse
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent import DeepSeekChatClient
from scienceworld_retrieval import EMBEDDER_NAME, retrieve
from scienceworld_skills import (
    ALL_GOLD_SKILLS,
    V4_GOLD_SKILLS,
    T_HORIZONTAL_SKILL_NAME,
    T_STRUCTURE_VERSION,
    T_VERTICAL_PATHS,
    library_hash,
    loaded_skill_text,
    t_skill_names,
    versioned_skills,
)


ACT_TOOL = {
    "type": "function",
    "function": {
        "name": "act",
        "description": "Send exactly one text command to the ScienceWorld environment.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
            "additionalProperties": False,
        },
    },
}

SYSTEM_PROMPT = """You control the ScienceWorld text environment. Complete the stated task by calling act with exactly one command at a time. Read the returned observation before choosing another action.

Useful command forms include: look around, inventory, task, go to <place>, open/close <object>, pick up <object>, move <object> to <destination>, focus on <object>, activate/deactivate <object>, examine <object>, use <tool> on <object>, pour <container> into <container>, wait, and wait1. Preserve the full object referent shown by the environment when similar objects exist.

Focus is a scored commitment: focusing on the wrong object can immediately end the episode with a negative score. Focus only on the exact task target, never its container or another sample of the same substance. If the environment asks you to disambiguate an action, send the requested number as the next command. The command wait advances ten environment moves; prefer wait1 unless ten moves are deliberately needed.

Do not invent observations or claim success. Only the environment score decides success. Stop issuing actions when done is true. The only available tool is act."""

V14B_PROTOCOL_VERSION = "scienceworld-v14b"
V14B_SYSTEM_PROMPT = SYSTEM_PROMPT + "\nOther available command forms: read <document>, mix <container>."
V14B_SHARED_CONTROLLER_VERSION = "shared-state-checkpoint-v1"

CONDITIONS = (
    "no_skill", "all_skills", "flat_retrieval", "body_aware_retrieval",
    "body_metadata_only", "body_placebo", "oracle_skill", "oracle_v2", "oracle_v3",
    "oracle_v3_full", "oracle_v3_metadata", "oracle_v3_placebo", "oracle_v4",
    "flat_retrieval_v4c", "body_aware_retrieval_v4c", "oracle_v4c",
    "flat_retrieval_v4d", "body_aware_retrieval_v4d", "oracle_v4d",
    "t_horizontal", "t_vertical", "t_full",
    "t2_horizontal", "t2_vertical", "t2_full",
    "t3_horizontal", "t3_vertical", "t3_full",
)
DEFAULT_CONDITIONS = ("no_skill", "oracle_v2")
AGENT_PROTOCOL_VERSION = "scienceworld-v2"
T2_CONTROLLER_VERSION = "repeated-action-guard-v1"
T3_CONTROLLER_VERSION = "state-aware-checkpoint-v1"
WAIT_COMMANDS = {"wait", "wait1"}
T3_WAIT_CHECKPOINT = 3
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
    gold_skills: List[str]
    library_version: Optional[str]


def objective_success(score: int) -> bool:
    """ScienceWorld exposes normalized task score on a 0--100 scale."""
    return score >= 100


def repeated_action_limit(command: str) -> int:
    normalized = " ".join(command.lower().split())
    return 8 if normalized == "wait1" else 2 if normalized == "wait" else 3


def skill_selection(condition: str, task_name: str, task_text: str = "") -> SkillSelection:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    if task_name not in ALL_GOLD_SKILLS:
        raise ValueError(f"no frozen Oracle label for task: {task_name}")
    is_new = task_name in V4_GOLD_SKILLS
    if condition.endswith(("_v4c", "_v4d")) and not is_new:
        raise ValueError("v4c and v4d conditions require a v14 task family")
    library_version = (
        "v4d" if condition.endswith("_v4d") else "v4c" if condition.endswith("_v4c") else "v4b"
    ) if is_new else "v3"
    gold = [ALL_GOLD_SKILLS[task_name]]
    if condition == "no_skill":
        return SkillSelection([], [], [], None, gold, None)
    if condition == "all_skills":
        return SkillSelection([item.name for item in versioned_skills(library_version)], [], [], None, gold, library_version)
    if condition in {
        "t_horizontal", "t_vertical", "t_full",
        "t2_horizontal", "t2_vertical", "t2_full",
        "t3_horizontal", "t3_vertical", "t3_full",
    }:
        if is_new:
            raise ValueError("T-shaped conditions are defined only for the original six task families")
        names = list(t_skill_names(condition, task_name))
        return SkillSelection(names, [], [], None, gold, T_STRUCTURE_VERSION if names else None)
    if condition in {"oracle_v4", "oracle_v4c", "oracle_v4d"}:
        if not is_new:
            raise ValueError("v4 Oracle conditions are defined only for the four v14 task families")
        return SkillSelection(gold, [], [], None, gold, library_version)
    if condition in {
        "oracle_skill", "oracle_v2", "oracle_v3",
        "oracle_v3_full", "oracle_v3_metadata", "oracle_v3_placebo",
    }:
        if is_new:
            raise ValueError("older Oracle conditions have no Skill for this v14 task family")
        version = {
            "oracle_skill": "v1",
            "oracle_v2": "v2",
            "oracle_v3": "v3",
            "oracle_v3_full": "v3",
            "oracle_v3_metadata": "v3",
            "oracle_v3_placebo": "v3",
        }[condition]
        return SkillSelection(gold, [], [], None, gold, version)
    body_aware = condition in {"body_aware_retrieval", "body_aware_retrieval_v4c", "body_aware_retrieval_v4d", "body_metadata_only", "body_placebo"}
    hits = retrieve(task_text, body_aware=body_aware, version=library_version)
    ranks = {item.name: item.rank for item in hits}
    return SkillSelection(
        [item.name for item in hits],
        [asdict(item) for item in hits],
        [ranks.get(name) for name in gold],
        EMBEDDER_NAME,
        gold,
        library_version,
    )


def skill_names(condition: str, task_name: str) -> List[str]:
    return skill_selection(condition, task_name).names


def calculate_cost(model: str, metrics: Dict[str, int]):
    price = PRICING_PER_MILLION.get(model)
    if price is None:
        return None
    return (
        metrics["prompt_cache_hit_tokens"] * price["cache_hit"]
        + metrics["prompt_cache_miss_tokens"] * price["cache_miss"]
        + metrics["output_tokens"] * price["output"]
    ) / 1_000_000


def make_env(max_steps: int):
    from scienceworld import ScienceWorldEnv

    return ScienceWorldEnv("", envStepLimit=max_steps)


def run_gold_check(task_name: str, variation: int, simplification: str, max_steps: int) -> Dict[str, Any]:
    env = make_env(max_steps)
    trace = []
    try:
        env.load(task_name, variationIdx=variation, simplificationStr=simplification, generateGoldPath=True)
        _, info = env.reset()
        done = False
        environment_moves = info["moves"]
        for command in env.get_gold_action_sequence():
            if done or len(trace) >= max_steps:
                break
            observation, reward, done, info = env.step(command)
            environment_moves = info["moves"]
            trace.append({"command": command, "observation": observation, "reward": reward, "score": info["score"], "done": done, "environment_moves": environment_moves})
        return {
            "environment": "scienceworld",
            "condition": "gold_control",
            "task_id": f"{task_name}:v{variation:03d}",
            "task_name": task_name,
            "variation": variation,
            "simplification": simplification,
            "success": objective_success(info["score"]),
            "done": done,
            "score": info["score"],
            "steps": len(trace),
            "environment_moves": environment_moves,
            "trace": trace,
        }
    finally:
        env.close()


def run_episode(
    model: str,
    temperature: float,
    task_name: str,
    variation: int,
    simplification: str,
    max_steps: int,
    condition: str,
) -> Dict[str, Any]:
    env = make_env(max_steps)
    started = time.perf_counter()
    trace: List[Dict[str, Any]] = []
    try:
        env.load(task_name, variationIdx=variation, simplificationStr=simplification)
        observation, info = env.reset()
        task_description = info["taskDesc"]
        selection = skill_selection(condition, task_name, task_description)
        selected = selection.names
        skill_version = selection.library_version
        skill_render_mode = {
            "body_metadata_only": "metadata_only",
            "body_placebo": "placebo",
            "oracle_v3_metadata": "metadata_only",
            "oracle_v3_placebo": "placebo",
        }.get(condition, "full")
        skill_prompt = loaded_skill_text(selected, skill_version, skill_render_mode) if selected else ""
        is_t_condition = condition in {
            "t_horizontal", "t_vertical", "t_full",
            "t2_horizontal", "t2_vertical", "t2_full",
            "t3_horizontal", "t3_vertical", "t3_full",
        }
        horizontal_loaded = condition in {
            "t_horizontal", "t_full", "t2_horizontal", "t2_full", "t3_horizontal", "t3_full",
        }
        vertical_loaded = condition in {
            "t_vertical", "t_full", "t2_vertical", "t2_full", "t3_vertical", "t3_full",
        }
        controller_version = (
            V14B_SHARED_CONTROLLER_VERSION if task_name in V4_GOLD_SKILLS
            else T2_CONTROLLER_VERSION if condition in {"t2_horizontal", "t2_full"}
            else T3_CONTROLLER_VERSION if condition in {"t3_horizontal", "t3_full"}
            else None
        )
        state_aware_controller = controller_version in {T3_CONTROLLER_VERSION, V14B_SHARED_CONTROLLER_VERSION}
        vertical_path = T_VERTICAL_PATHS[task_name] if vertical_loaded else ()
        messages: List[Dict[str, Any]] = [{"role": "system", "content": V14B_SYSTEM_PROMPT if task_name in V4_GOLD_SKILLS else SYSTEM_PROMPT}]
        if selected:
            messages.append({"role": "system", "content": "Fixed Skill guidance:\n" + skill_prompt})
        messages.append({
            "role": "user",
            "content": f"Task:\n{task_description}\n\nInitial observation:\n{observation}",
        })
        client = DeepSeekChatClient(model, temperature, tools=[ACT_TOOL])
        done = False
        score = info["score"]
        environment_moves = info["moves"]
        final_text = ""
        llm_calls = 0
        controller_interventions = 0
        environment_actions = 0
        last_command = ""
        repeated_without_progress = 0
        consecutive_waits = 0
        consecutive_rejections = 0
        stalled = False

        while len(trace) < max_steps and not done:
            reply = client.respond(messages)
            llm_calls += 1
            messages.append(reply)
            calls = reply.get("tool_calls") or []
            if not calls:
                final_text = reply.get("content") or ""
                break
            call = calls[0]
            command = ""
            try:
                if call.get("function", {}).get("name") != "act":
                    raise ValueError("the only available tool is act(command)")
                arguments = json.loads(call["function"]["arguments"])
                command = arguments["command"]
                if not isinstance(command, str) or not command.strip():
                    raise ValueError("command must be a non-empty string")
                normalized_command = " ".join(command.lower().split())
                wait_checkpoint = (
                    state_aware_controller
                    and normalized_command in WAIT_COMMANDS
                    and consecutive_waits >= T3_WAIT_CHECKPOINT
                )
                repeated_stagnation = (
                    controller_version is not None
                    and normalized_command not in WAIT_COMMANDS
                    and normalized_command == last_command
                    and repeated_without_progress >= repeated_action_limit(normalized_command)
                )
                t2_repeated_wait = (
                    controller_version == T2_CONTROLLER_VERSION
                    and normalized_command in WAIT_COMMANDS
                    and normalized_command == last_command
                    and repeated_without_progress >= repeated_action_limit(normalized_command)
                )
                if wait_checkpoint or repeated_stagnation or t2_repeated_wait:
                    controller_interventions += 1
                    consecutive_rejections += 1
                    stalled = controller_version == V14B_SHARED_CONTROLLER_VERSION and consecutive_rejections >= 3
                    reason = "wait_checkpoint" if wait_checkpoint else "repeated_unchanged_action"
                    error = (
                        "Three consecutive wait actions were completed. Before waiting again, inspect the task-relevant sample or device with examine <object> so hidden state changes are observable."
                        if wait_checkpoint else
                        "Horizontal progress controller blocked a repeated no-progress command. Do not repeat it. Inspect the target, container, inventory, current state, and unmet prerequisite before choosing a different action."
                    )
                    result = {
                        "ok": False,
                        "error": error,
                        "controller": controller_version,
                        "reason": reason,
                        "state_summary": {
                            "score": score,
                            "environment_moves": environment_moves,
                            "last_observation": observation[:240],
                        },
                        "score": score,
                        "done": done,
                        "environment_moves": environment_moves,
                    }
                else:
                    consecutive_rejections = 0
                    previous_score = score
                    previous_observation = observation
                    observation, reward, done, info = env.step(command)
                    environment_actions += 1
                    score = info["score"]
                    environment_moves = info["moves"]
                    unchanged = score == previous_score and (
                        not state_aware_controller or observation == previous_observation
                    )
                    if normalized_command == last_command and unchanged:
                        repeated_without_progress += 1
                    elif unchanged:
                        repeated_without_progress = 1
                    else:
                        repeated_without_progress = 0
                    if state_aware_controller:
                        if normalized_command in WAIT_COMMANDS:
                            consecutive_waits += 1
                        elif normalized_command.startswith("examine ") or normalized_command in {"look around", "inventory"}:
                            consecutive_waits = 0
                    last_command = normalized_command
                    result = {
                        "ok": True,
                        "observation": observation,
                        "reward": reward,
                        "score": score,
                        "done": done,
                        "environment_moves": environment_moves,
                    }
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                result = {"ok": False, "error": str(error), "score": score, "done": done, "environment_moves": environment_moves}
            trace.append({"tool": "act", "command": command, "result": result})
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id", "missing-call-id"),
                "content": json.dumps(result, ensure_ascii=False),
            })
            for ignored_call in calls[1:]:
                messages.append({
                    "role": "tool",
                    "tool_call_id": ignored_call.get("id", "missing-call-id"),
                    "content": json.dumps({
                        "ok": False,
                        "error": "not executed: call act once per turn and read its observation before the next action",
                    }),
                })
            if stalled:
                break

        metrics = client.metrics()
        return {
            "environment": "scienceworld",
            "task_id": f"{task_name}:v{variation:03d}",
            "task_name": task_name,
            "variation": variation,
            "simplification": simplification,
            "max_steps": max_steps,
            "condition": condition,
            "agent_protocol_version": V14B_PROTOCOL_VERSION if task_name in V4_GOLD_SKILLS else AGENT_PROTOCOL_VERSION,
            "model": model,
            "temperature": temperature,
            "success": objective_success(score),
            "done": done,
            "score": score,
            "steps": len(trace),
            "environment_moves": environment_moves,
            "llm_calls": llm_calls,
            "tool_calls": len(trace),
            "environment_actions": environment_actions,
            "input_tokens": metrics["input_tokens"],
            "output_tokens": metrics["output_tokens"],
            "total_tokens": metrics["input_tokens"] + metrics["output_tokens"],
            "prompt_cache_hit_tokens": metrics["prompt_cache_hit_tokens"],
            "prompt_cache_miss_tokens": metrics["prompt_cache_miss_tokens"],
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "cost_usd": calculate_cost(model, metrics),
            "skills_loaded": selected,
            "gold_skills": selection.gold_skills,
            "gold_skill_ranks": selection.gold_skill_ranks,
            "retriever": selection.retriever,
            "retrieval_query": task_description,
            "retrieval": selection.retrieved,
            "retrieval_rank": min((rank for rank in selection.gold_skill_ranks if rank is not None), default=None),
            "skill_library_version": skill_version,
            "skill_library_sha256": library_hash(skill_version) if skill_version else None,
            "skill_render_mode": skill_render_mode if selected else None,
            "skill_prompt_sha256": hashlib.sha256(skill_prompt.encode("utf-8")).hexdigest() if selected else None,
            "skill_architecture": "t_shaped" if is_t_condition else ("none" if condition == "no_skill" else "flat"),
            "structure_version": (
                "t3" if condition.startswith("t3_") else
                "t2" if condition.startswith("t2_") else
                T_STRUCTURE_VERSION if is_t_condition else None
            ),
            "horizontal_layer_loaded": horizontal_loaded,
            "horizontal_skills_loaded": [T_HORIZONTAL_SKILL_NAME] if T_HORIZONTAL_SKILL_NAME in selected else [],
            "vertical_layer_loaded": vertical_loaded,
            "vertical_domain": vertical_path[0] if vertical_path else None,
            "vertical_path": list(vertical_path),
            "vertical_depth": len(vertical_path),
            "skill_prompt_words": len(skill_prompt.split()),
            "skill_prompt_characters": len(skill_prompt),
            "horizontal_controller_version": controller_version if is_t_condition else None,
            "shared_controller_version": controller_version if task_name in V4_GOLD_SKILLS else None,
            "controller_interventions": controller_interventions,
            "termination_reason": "controller_stall" if stalled else "environment_done" if done else "max_steps" if len(trace) >= max_steps else "model_stopped",
            "final_text": final_text,
            "trace": trace,
        }
    finally:
        env.close()


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one objectively scored ScienceWorld episode")
    parser.add_argument("--model", help="DeepSeek model ID; required for an API episode")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--task", choices=tuple(ALL_GOLD_SKILLS), default="boil")
    parser.add_argument("--variation", type=int, default=0)
    parser.add_argument("--simplification", default="easy")
    parser.add_argument("--condition", choices=CONDITIONS, default="no_skill")
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--results", type=Path, default=Path("results/scienceworld_results.jsonl"))
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--smoke", action="store_true", help="load and reset one local task; no API call")
    parser.add_argument("--gold-check", action="store_true", help="replay ScienceWorld's generated gold path; no API call")
    args = parser.parse_args()
    if args.variation < 0 or args.max_steps < 1:
        parser.error("--variation must be non-negative and --max-steps must be positive")
    if args.gold_check:
        print(json.dumps(run_gold_check(args.task, args.variation, args.simplification, args.max_steps), ensure_ascii=False, indent=2))
        return 0
    if args.smoke:
        env = make_env(args.max_steps)
        try:
            env.load(args.task, variationIdx=args.variation, simplificationStr=args.simplification)
            observation, info = env.reset()
            print(json.dumps({
                "environment": "scienceworld",
                "task_id": f"{args.task}:v{args.variation:03d}",
                "score": info["score"],
                "environment_moves": info["moves"],
                "done": False,
                "task": info["taskDesc"],
                "observation": observation,
            }, ensure_ascii=False, indent=2))
        finally:
            env.close()
        return 0
    if not args.model:
        parser.error("--model is required unless --smoke or --gold-check is used")
    record = run_episode(
        args.model, args.temperature, args.task, args.variation,
        args.simplification, args.max_steps, args.condition,
    )
    record.update({
        "schema_version": 1,
        "run_id": args.run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "repeat": 0,
        "thinking": "disabled",
    })
    append_jsonl(args.results, record)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
