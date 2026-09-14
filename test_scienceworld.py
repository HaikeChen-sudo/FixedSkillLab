import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scienceworld_agent import CONDITIONS, DEFAULT_CONDITIONS, objective_success, run_episode, skill_names, skill_selection
from scienceworld_retrieval import EMBEDDER_NAME, retrieve
from scienceworld_experiment import PILOT_TASKS, completed_episodes, experiment_cases
from scienceworld_skills import GOLD_SKILLS, SKILL_LIST, V2_SKILL_OVERRIDES, V3_SKILL_OVERRIDES, library_hash, loaded_skill_text, validate_library
from analyze_scienceworld_formal import exact_sign_p_value, validation_errors
from scienceworld_suites import SCIENCEWORLD_PILOT_6, SCIENCEWORLD_V3_HELDOUT_6, SCIENCEWORLD_V4_HELDOUT_6, SCIENCEWORLD_V6_ROUTER_FORMAL_12, SUITE_VARIATION_SPLITS, validate_suites


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

    def test_v4_suite_was_frozen_before_oracle_v3(self):
        self.assertEqual(SCIENCEWORLD_V4_HELDOUT_6, (
            ("boil", 22), ("melt", 22), ("freeze", 22),
            ("use-thermometer", 406), ("find-living-thing", 226),
            ("find-non-living-thing", 226),
        ))
        self.assertFalse(set(SCIENCEWORLD_V3_HELDOUT_6) & set(SCIENCEWORLD_V4_HELDOUT_6))
        rows = [json.loads(line) for line in Path("results/scienceworld_v4_heldout_manifest.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row["frozen_before_oracle_v3"] and row["gold_success"] and row["gold_score"] == 100 for row in rows))
        self.assertEqual({row["gold_check_max_steps"] for row in rows}, {200})

    def test_v6_router_suite_is_new_and_preregistered(self):
        self.assertEqual(SCIENCEWORLD_V6_ROUTER_FORMAL_12, (
            ("boil", 23), ("boil", 24), ("melt", 23), ("melt", 24),
            ("freeze", 23), ("freeze", 24),
            ("use-thermometer", 407), ("use-thermometer", 408),
            ("find-living-thing", 227), ("find-living-thing", 228),
            ("find-non-living-thing", 227), ("find-non-living-thing", 228),
        ))
        earlier = set(SCIENCEWORLD_PILOT_6) | set(SCIENCEWORLD_V3_HELDOUT_6) | set(SCIENCEWORLD_V4_HELDOUT_6)
        self.assertFalse(earlier & set(SCIENCEWORLD_V6_ROUTER_FORMAL_12))
        rows = [json.loads(line) for line in Path("results/scienceworld_v6_router_manifest.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(row["task_name"], row["variation"]) for row in rows], list(SCIENCEWORLD_V6_ROUTER_FORMAL_12))
        self.assertTrue(all(row["frozen_before_gold_check"] and row["gold_success"] is None for row in rows))
        gold = [json.loads(line) for line in Path("results/scienceworld_v6_gold_validation.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(row["task_name"], row["variation"]) for row in gold], list(SCIENCEWORLD_V6_ROUTER_FORMAL_12))
        self.assertTrue(all(row["gold_success"] and row["gold_score"] == 100 and row["formal_max_steps"] == 400 for row in gold))
        self.assertLessEqual(max(row["gold_environment_moves"] for row in gold), 400)
        audit = [json.loads(line) for line in Path("results/scienceworld_v6_router_offline.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sum(row["flat_gold_rank"] is not None for row in audit), 8)
        self.assertEqual(sum(row["body_gold_rank"] is not None for row in audit), 10)

    def test_formal_v3_data_is_complete_and_immutable(self):
        path = Path("results/formal_scienceworld_v3/scienceworld-v3-heldout-6x3.jsonl")
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(validation_errors(records, "scienceworld-v3-heldout-6", ("no_skill", "oracle_v2"), 3), [])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), "d9aa310b50395bce111e23e851a11f0ea6b372aad0f0a8561546a9bc76929f1e")

    def test_formal_v4_data_is_complete_and_immutable(self):
        path = Path("results/formal_scienceworld_v4/scienceworld-v4-heldout-6x3.jsonl")
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(validation_errors(records, "scienceworld-v4-heldout-6", ("no_skill", "oracle_v2", "oracle_v3"), 3), [])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), "4357856023e93471020852dadf6184cba024506e7b283ad2417579a56469906e")

    def test_formal_v6_data_is_complete_and_immutable(self):
        path = Path("results/formal_scienceworld_v6/scienceworld-v6-router-formal-12x3.jsonl")
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        conditions = ("no_skill", "all_skills", "flat_retrieval", "body_aware_retrieval", "oracle_v3")
        self.assertEqual(validation_errors(records, "scienceworld-v6-router-formal-12", conditions, 3), [])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), "c978ce0568f89fecaff48848327817cdd3493a18162df1bc0b99bcdaf9b043fd")
        self.assertEqual(exact_sign_p_value(9, 1), 0.021484375)

    def test_conditions_change_only_loaded_skill(self):
        self.assertEqual(skill_names("no_skill", "boil"), [])
        self.assertEqual(skill_names("oracle_skill", "boil"), ["boil-substance"])
        self.assertEqual(skill_selection("oracle_v2", "boil").names, ["boil-substance"])
        self.assertEqual(skill_selection("oracle_v2", "boil").library_version, "v2")
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

    def test_v3_fixes_only_the_state_change_workflows(self):
        self.assertEqual(set(V3_SKILL_OVERRIDES), {"boil-substance", "melt-substance", "freeze-substance"})
        self.assertEqual(skill_selection("oracle_v3", "boil").names, ["boil-substance"])
        self.assertIn("solid to liquid is only melting", loaded_skill_text(["boil-substance"], "v3"))
        self.assertIn("never try to freeze an already-solid sample", loaded_skill_text(["freeze-substance"], "v3"))
        self.assertEqual(library_hash("v3"), "fdd9d917af6528933d71f744e57b88aae6e7e52113354e20bec3ffbf8cd0f322")

    def test_router_conditions_load_v3_skills_and_record_rank(self):
        self.assertTrue({"all_skills", "flat_retrieval", "body_aware_retrieval"} <= set(CONDITIONS))
        self.assertEqual(len(skill_selection("all_skills", "boil").names), 6)
        for condition in ("flat_retrieval", "body_aware_retrieval"):
            selection = skill_selection(condition, "boil", "Your task is to boil tin.")
            self.assertEqual(len(selection.names), 3)
            self.assertEqual(selection.library_version, "v3")
            self.assertEqual(selection.retriever, EMBEDDER_NAME)
            self.assertEqual(selection.gold_skill_ranks[0], next(item.rank for item in retrieve("Your task is to boil tin.", condition == "body_aware_retrieval") if item.name == "boil-substance"))

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
