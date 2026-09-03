"""Minimal model-driven Mini Lab agent. Skills are deliberately not used here."""

import argparse
import http.client
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from minilab import MiniLab, TOOL_HELP, ToolError
from tasks import TASKS


SYSTEM_PROMPT = """You solve Mini Lab tasks by calling the provided tool functions.
Use only the provided tool names and arguments. Inspect files before relying on their contents.
Do not invent tool results. Do not discuss grading or claim success: the host grades after you stop.
For tasks asking for an answer, call submit with the answer. When the task gives an Answer JSON type, match it exactly; a code made of digits can still be a string. For file-output tasks, stop after completing the requested file operations."""


def _tool_schema(name: str, description: str) -> Dict[str, Any]:
    parameters: Dict[str, Any] = {"type": "object", "additionalProperties": True}
    if name == "submit":
        parameters = {
            "type": "object",
            "properties": {
                "value": {"oneOf": [
                    {"type": "number"}, {"type": "string"}, {"type": "boolean"},
                    {"type": "null"}, {"type": "array"}, {"type": "object"},
                ]},
            },
            "required": ["value"],
            "additionalProperties": False,
        }
    return {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}


TOOL_SCHEMAS = [_tool_schema(name, description) for name, description in sorted(TOOL_HELP.items())]


@dataclass
class Episode:
    task_id: str
    success: bool
    steps: int
    final_text: str
    trace: List[Dict[str, Any]]
    llm_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0
    latency_ms: int = 0


def initial_messages(task: Dict[str, Any], skill_text: str = "") -> List[Dict[str, Any]]:
    """Keep the machine-checkable target out of the model context."""
    answer_type = task.get("answer_json_type")
    answer_contract = f"\n\nAnswer JSON type for submit: {answer_type}" if answer_type else ""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "Task:\n" + task["instruction"] + answer_contract + "\n\nAvailable tools:\n" + json.dumps(TOOL_HELP, ensure_ascii=False),
        },
    ]
    if skill_text:
        messages.append({
            "role": "user",
            "content": "Fixed Skill guidance:\n" + skill_text + "\n\nThese Skills add no tools and do not reveal the grader.",
        })
    return messages


class DeepSeekChatClient:
    """Thin DeepSeek Chat Completions client using urllib and no SDK."""

    endpoint = "https://api.deepseek.com/chat/completions"

    def __init__(
        self,
        model: str,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ):
        self.model = model
        self.temperature = temperature
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self.tools = tools or TOOL_SCHEMAS
        if not self.api_key:
            raise ValueError("set DEEPSEEK_API_KEY before running the deepseek command")
        self.input_tokens = 0
        self.output_tokens = 0
        self.prompt_cache_hit_tokens = 0
        self.prompt_cache_miss_tokens = 0

    def respond(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "tools": self.tools,
            "tool_choice": "auto",
            "temperature": self.temperature,
            "thinking": {"type": "disabled"},
        }).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = json.load(response)
                break
            except urllib.error.HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                    detail = error.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"DeepSeek API returned HTTP {error.code}: {detail}") from error
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as error:
                if attempt == 3:
                    raise RuntimeError(f"DeepSeek API request failed: {error}") from error
            time.sleep(2 ** attempt)
        try:
            usage = payload.get("usage") or {}
            self.input_tokens += usage.get("prompt_tokens", 0)
            self.output_tokens += usage.get("completion_tokens", 0)
            self.prompt_cache_hit_tokens += usage.get("prompt_cache_hit_tokens", 0)
            self.prompt_cache_miss_tokens += usage.get("prompt_cache_miss_tokens", usage.get("prompt_tokens", 0))
            return payload["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError(f"unexpected DeepSeek API response: {payload}") from error

    def metrics(self) -> Dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "prompt_cache_hit_tokens": self.prompt_cache_hit_tokens,
            "prompt_cache_miss_tokens": self.prompt_cache_miss_tokens,
        }


class ReferenceReplayClient:
    """Local smoke-test client; it replays task reference actions and is not a benchmark model."""

    def __init__(self, task_id: str):
        self.actions = iter(TASKS[task_id].reference)

    def respond(self, _messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            action = next(self.actions)
        except StopIteration:
            return {"role": "assistant", "content": "done"}
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": f"replay-{action['tool']}",
                "type": "function",
                "function": {"name": action["tool"], "arguments": json.dumps(action["args"])},
            }],
        }


class Agent:
    def __init__(self, client: Any):
        self.client = client

    def run(self, task_id: str, skill_text: str = "") -> Episode:
        trace: List[Dict[str, Any]] = []
        with MiniLab() as lab:
            task = lab.reset(task_id)
            messages = initial_messages(task, skill_text)
            final_text = ""
            llm_calls = 0
            started = time.perf_counter()
            while lab.steps < task["max_steps"]:
                assistant_message = self.client.respond(messages)
                llm_calls += 1
                messages.append(assistant_message)
                calls = assistant_message.get("tool_calls") or []
                if not calls:
                    final_text = assistant_message.get("content") or ""
                    break
                submitted = False
                for call in calls:
                    result, tool_name = self._execute(lab, call)
                    trace.append({"tool": tool_name, "result": result})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", "missing-call-id"),
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                    submitted = submitted or tool_name == "submit"
                if submitted:
                    break
            grade = lab.grade()
            metrics = getattr(self.client, "metrics", lambda: {})()
            return Episode(
                task_id=task_id,
                success=grade["success"],
                steps=llm_calls,
                final_text=final_text,
                trace=trace,
                llm_calls=llm_calls,
                tool_calls=len(trace),
                input_tokens=metrics.get("input_tokens", 0),
                output_tokens=metrics.get("output_tokens", 0),
                prompt_cache_hit_tokens=metrics.get("prompt_cache_hit_tokens", 0),
                prompt_cache_miss_tokens=metrics.get("prompt_cache_miss_tokens", 0),
                latency_ms=round((time.perf_counter() - started) * 1000),
            )

    @staticmethod
    def _execute(lab: MiniLab, call: Dict[str, Any]) -> tuple:
        try:
            tool_name = call["function"]["name"]
            if call.get("type") != "function" or tool_name not in TOOL_HELP:
                raise ToolError(f"unknown tool: {tool_name}")
            arguments = json.loads(call["function"]["arguments"])
            if not isinstance(arguments, dict):
                raise ToolError("tool args must be an object")
            return {"ok": True, "result": lab.call_tool(tool_name, **arguments)}, tool_name
        except (json.JSONDecodeError, KeyError, TypeError, ToolError, OSError, ValueError) as error:
            return {"ok": False, "error": str(error)}, "invalid"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a minimal tool-using Mini Lab agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    replay = subparsers.add_parser("replay", help="run local reference actions through the agent loop")
    replay.add_argument("task_id", choices=TASKS)
    deepseek = subparsers.add_parser("deepseek", help="run one task with the DeepSeek Chat Completions API")
    deepseek.add_argument("task_id", choices=TASKS)
    deepseek.add_argument("--model", required=True, help="exact model ID available to your DeepSeek API account")
    deepseek.add_argument("--temperature", type=float, default=0.0)
    args = parser.parse_args()

    client = ReferenceReplayClient(args.task_id) if args.command == "replay" else DeepSeekChatClient(args.model, args.temperature)
    print(json.dumps(asdict(Agent(client).run(args.task_id)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
