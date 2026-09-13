import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scienceworld_agent import DEFAULT_CONDITIONS, objective_success, run_episode, skill_names, skill_selection
from scienceworld_experiment import PILOT_TASKS, completed_episodes, experiment_cases
from scienceworld_skills import GOLD_SKILLS, SKILL_LIST, V2_SKILL_OVERRIDES, library_hash, loaded_skill_text, validate_library
from scienceworld_suites import SCIENCEWORLD_PILOT_6, SCIENCEWORLD_V3_HELDOUT_6, SUITE_VARIATION_SPLITS, validate_suites


class ScienceWorldTests(unittest.TestCase):
    def test_pilot_has_six_fixed_oracle_skills(self):
        self.assertEqual(validate_library(), [])
        self.assertEqual(len(PILOT_TASKS), 6)
        self.assertEqual(set(PILOT_TASKS), set(GOLD_SKILLS))
        self.assertEqual(len(SKILL_LIST), 6)

    def test_heldout_suite_uses_frozen_test_variations(self):
        self.assertEqual(validate_suites(), [])
        self.assertEqual(SCIENCEWORLD_PILOT_6, tuple((task, 0) for task in GOLD_SKILLS))
        self.assertEqual(SCIENCEWORLD_V3_HELDOUT_6, (
            ("boil", 21), ("melt", 21), ("freeze", 21),
            ("use-thermometer", 405), ("find-living-thing", 225),
            ("find-non-living-thing", 225),
        ))
        self.assertEqual(SUITE_VARIATION_SPLITS["scienceworld-v3-heldout-6"], "test")
        self.assertEqual(experiment_cases("scienceworld-v3-heldout-6", None, None), list(SCIENCEWORLD_V3_HELDOUT_6))
        with self.assertRaises(ValueError):
            experiment_cases("scienceworld-v3-heldout-6", ["boil"], None)

    def test_conditions_change_only_loaded_skill(self):
        self.assertEqual(skill_names("no_skill", "boil"), [])
        self.assertEqual(skill_names("oracle_skill", "boil"), ["boil-substance"])
        self.assertEqual(skill_selection("oracle_v2", "boil"), (["boil-substance"], "v2"))
        self.assertEqual(DEFAULT_CONDITIONS, ("no_skill", "oracle_v2"))
        rendered = loaded_skill_text(["boil-substance"])
        for heading in ("Name", "Description", "Activation Condition", "Procedure", "Termination Condition"):
            self.assertIn(heading, rendered)

    def test_v2_preserves_v1_and_changes_only_failed_skill_families(self):
        self.assertEqual(set(V2_SKILL_OVERRIDES), {"melt-substance", "freeze-substance", "find-living-object"})
        self.assertEqual(library_hash("v1"), "b0d48936176047bf0b290bcde30cadcbe13580a7870fee62e6d0a770b241c2ca")
        self.assertNotEqual(library_hash("v1"), library_hash("v2"))
        self.assertIn("never focus on its flower pot", loaded_skill_text(["find-living-object"], "v2"))
        self.assertIn("wait1 rather than wait", loaded_skill_text(["freeze-substance"], "v2"))

    def test_environment_score_is_the_only_success_rule(self):
        self.assertFalse(objective_success(-1))
        self.assertFalse(objective_success(99))
        self.assertTrue(objective_success(100))

    def test_resume_uses_task_variation_condition_and_repeat(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            row = {"run_id": "pilot", "task_name": "boil", "variation": 0, "condition": "no_skill", "repeat": 0}
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            self.assertEqual(completed_episodes(path, "pilot"), {("boil", 0, "no_skill", 0)})

    def test_multiple_act_calls_receive_responses_without_extra_environment_steps(self):
        class FakeEnv:
            def __init__(self):
                self.commands = []

            def load(self, *_args, **_kwargs):
                pass

            def reset(self):
                return "room", {"taskDesc": "test", "score": 0, "moves": 0}

            def step(self, command):
                self.commands.append(command)
                return f"ran {command}", 0, False, {"score": 0, "moves": 1}

            def close(self):
                pass

        class MultipleActClient:
            def __init__(self, *_args, **_kwargs):
                self.turn = 0

            def respond(self, messages):
                if self.turn == 0:
                    self.turn += 1
                    return {"role": "assistant", "content": None, "tool_calls": [
                        {"id": "call-1", "type": "function", "function": {"name": "act", "arguments": '{"command":"look around"}'}},
                        {"id": "call-2", "type": "function", "function": {"name": "act", "arguments": '{"command":"inventory"}'}},
                    ]}
                assistant_index = max(index for index, message in enumerate(messages) if message["role"] == "assistant")
                expected = {call["id"] for call in messages[assistant_index]["tool_calls"]}
                answered = {message["tool_call_id"] for message in messages[assistant_index + 1:] if message["role"] == "tool"}
                if answered != expected:
                    raise RuntimeError("insufficient tool messages following tool_calls")
                return {"role": "assistant", "content": "done"}

            def metrics(self):
                return {"input_tokens": 0, "output_tokens": 0, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0}

        env = FakeEnv()
        with patch("scienceworld_agent.make_env", return_value=env), patch("scienceworld_agent.DeepSeekChatClient", MultipleActClient):
            record = run_episode("test", 0, "boil", 0, "easy", 5, "no_skill")
        self.assertEqual(env.commands, ["look around"])
        self.assertEqual(record["tool_calls"], 1)


if __name__ == "__main__":
    unittest.main()
