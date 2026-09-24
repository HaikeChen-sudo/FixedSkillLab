"""Budget, preview and resume checks; fake environments and clients only."""

import contextlib
import io
import hashlib
import json
import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import scienceworld_agent as agent
import scienceworld_budget_pilot as pilot
import scienceworld_experiment as experiment
from scienceworld_skills import library_hash, loaded_skill_text, versioned_skills


class FakeEnv:
    def __init__(self, limit):
        self.limit = limit
        self.moves = 0

    def load(self, *_args, **_kwargs):
        pass

    def reset(self):
        self.moves = 0
        return "room", {"taskDesc": "test", "score": 0, "moves": 0}

    def step(self, command):
        self.moves += 11
        return command, 0, self.moves > self.limit, {"score": 0, "moves": self.moves}

    def get_gold_action_sequence(self):
        return ["wait"] * 5

    def close(self):
        pass


class FakeClient:
    def __init__(self, *_args, **_kwargs):
        pass

    def respond(self, messages):
        return {"role": "assistant", "tool_calls": [{"id": str(len(messages)), "type": "function",
                "function": {"name": "act", "arguments": '{"command":"wait"}'}}]}

    def metrics(self):
        return dict(input_tokens=10, output_tokens=1, prompt_cache_hit_tokens=0, prompt_cache_miss_tokens=10)


def fake_episode(model, temperature, task, variation, simplification, steps, condition, *, environment_max_steps):
    names = [] if condition == "no_skill" else [skill.name for skill in versioned_skills("v4d")][:3]
    return dict(model=model, temperature=temperature, task_name=task, variation=variation,
                task_id=f"{task}:v{variation:03d}", simplification=simplification, condition=condition,
                max_steps=steps, agent_max_steps=steps, environment_max_steps=environment_max_steps,
                budget_protocol_version="split-budgets-v1", score=100, success=True,
                input_tokens=10, output_tokens=1, total_tokens=11, latency_ms=1, cost_usd=0.001,
                retrieval_query="same query", skills_loaded=names,
                skill_prompt_sha256=hashlib.sha256(loaded_skill_text(names, "v4d").encode()).hexdigest() if names else None,
                skill_library_sha256=library_hash("v4d") if names else None)


class BudgetTests(unittest.TestCase):
    def test_independent_caps_and_legacy_default(self):
        with patch.object(agent, "make_env", side_effect=FakeEnv), patch.object(agent, "DeepSeekChatClient", FakeClient):
            legacy = agent.run_episode("test", 0, "boil", 0, "easy", 3, "no_skill")
            explicit = agent.run_episode("test", 0, "boil", 0, "easy", 3, "no_skill", environment_max_steps=3)
            expanded = agent.run_episode("test", 0, "boil", 0, "easy", 3, "no_skill", environment_max_steps=100)
            intermediate = agent.run_episode("test", 0, "boil", 0, "easy", 3, "no_skill", environment_max_steps=20)
            self.assertEqual(legacy["trace"], explicit["trace"])
            self.assertEqual(legacy["steps"], 1)
            self.assertEqual(intermediate["steps"], 2)
            self.assertTrue(intermediate["environment_budget_exhausted"])
            self.assertFalse(intermediate["agent_budget_exhausted"])
            self.assertEqual(expanded["steps"], 3)
            self.assertTrue(expanded["agent_budget_exhausted"])
            self.assertFalse(expanded["environment_budget_exhausted"])
            self.assertEqual(expanded["termination_reason"], "max_steps")
            gold = agent.run_gold_check("boil", 0, "easy", 3, environment_max_steps=100)
            self.assertEqual(gold["steps"], 3)
            self.assertEqual(gold["environment_max_steps"], 100)

    def test_invalid_limits_fail_before_environment_or_api(self):
        for limit in (0, -1, True, 2.5):
            with self.subTest(limit=limit), patch.object(agent, "make_env") as make:
                with self.assertRaises(ValueError):
                    agent.run_episode("test", 0, "boil", 0, "easy", 100, "no_skill", environment_max_steps=limit)
                make.assert_not_called()

    def test_resume_distinguishes_legacy_and_changed_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rows.jsonl"
            row = dict(run_id="run", task_name="boil", variation=0, condition="no_skill", max_steps=100)
            agent.append_jsonl(path, row)
            self.assertEqual(len(experiment.completed_episodes(path, "run", {"environment_max_steps": 100})), 1)
            with self.assertRaisesRegex(ValueError, "environment_max_steps"):
                experiment.completed_episodes(path, "run", {"environment_max_steps": 200})

    def test_cli_forwards_environment_budget_in_single_batch_and_gold_modes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "rows.jsonl")
            common = ["--model", "test", "--max-steps", "100", "--environment-max-steps", "200", "--results", path]
            record = dict(task_id="boil:v000", success=True, score=100, latency_ms=1)
            with patch("sys.argv", ["scienceworld_agent.py"] + common), \
                    patch.object(agent, "run_episode", return_value=dict(record)) as run, \
                    patch.object(agent, "append_jsonl"), contextlib.redirect_stdout(io.StringIO()):
                agent.main()
                self.assertEqual(run.call_args.kwargs, {"environment_max_steps": 200})
            with patch("sys.argv", ["scienceworld_experiment.py", "--tasks", "boil", "--conditions", "no_skill"] + common), \
                    patch.object(experiment, "run_episode", return_value=dict(record)) as run, \
                    patch.object(experiment, "append_jsonl"), contextlib.redirect_stdout(io.StringIO()):
                experiment.main()
                self.assertEqual(run.call_args.kwargs, {"environment_max_steps": 200})
            gold_record = dict(record, steps=1, environment_moves=1)
            with patch("sys.argv", ["scienceworld_experiment.py", "--tasks", "boil", "--gold-check"] + common), \
                    patch.object(experiment, "run_gold_check", return_value=gold_record) as run, \
                    contextlib.redirect_stdout(io.StringIO()):
                experiment.main()
                self.assertEqual(run.call_args.kwargs, {"environment_max_steps": 200})

    def test_preview_and_plan(self):
        rows = pilot.plan()
        self.assertEqual(len(rows), 12)
        self.assertEqual(len({(r["variation"], r["condition"], r["environment_max_steps"]) for r in rows}), 12)
        self.assertEqual(Counter(r["environment_max_steps"] for r in rows[::2]), {100: 3, 200: 3})
        with patch.object(pilot, "preflight") as check, patch.object(pilot, "run_episode") as run, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            pilot.main([])
            self.assertEqual(json.loads(output.getvalue())["api_calls"], 0)
            check.assert_not_called()
            run.assert_not_called()

    def test_interruption_resume_and_duplicate_rejection(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(pilot, "MANIFEST", Path(folder) / "manifest.json"), \
                patch.object(pilot, "preflight"), patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-placeholder"}), \
                contextlib.redirect_stdout(io.StringIO()):
            path = Path(folder) / "results.jsonl"
            pilot.main(["--prepare", "--results", str(path)])
            calls = 0

            def interrupt(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise RuntimeError("interrupted")
                return fake_episode(*args, **kwargs)

            with patch.object(pilot, "run_episode", side_effect=interrupt):
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    pilot.main(["--execute", "--results", str(path)])
            self.assertEqual(len(path.read_text().splitlines()), 2)
            with patch.object(pilot, "run_episode", side_effect=fake_episode) as run:
                pilot.main(["--execute", "--resume", "--results", str(path)])
                self.assertEqual(run.call_count, 10)
                pilot.main(["--execute", "--resume", "--results", str(path)])
                self.assertEqual(run.call_count, 10)
            row = json.loads(path.read_text().splitlines()[0])
            row["environment_max_steps"] = 999
            with self.assertRaises(ValueError):
                pilot.validate_record(row, pilot.plan()[0], pilot.file_hash(pilot.MANIFEST))
            row = json.loads(path.read_text().splitlines()[0])
            agent.append_jsonl(path, row)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                pilot.saved_records(path, pilot.file_hash(pilot.MANIFEST))


if __name__ == "__main__":
    unittest.main()
