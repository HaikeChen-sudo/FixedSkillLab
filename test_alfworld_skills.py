import unittest

from alfworld_gold_skills import gold_skills_for_game
from alfworld_retrieval import BM25_RETRIEVER_NAME, retrieve, retrieve_bm25
from alfworld_skills import SKILL_LIST, SKILLS, validate_library
from alfworld_suites import ALFWORLD_V2_30, ALFWORLD_V3_HELDOUT_30, ALFWORLD_V5_TEST_30, SUITE_FAMILIES, validate_suites

try:
    from alfworld_agent import action_result
    from alfworld_experiment import completed_episodes
except ModuleNotFoundError:
    action_result = None
    completed_episodes = None


class AlfworldSkillTests(unittest.TestCase):
    def test_library_is_fixed_and_complete(self):
        self.assertEqual(len(SKILL_LIST), 30)
        self.assertEqual(validate_library(), [])

    def test_retrieval_returns_three_known_skills(self):
        hits = retrieve("put a heated apple in the garbagecan", body_aware=False)
        self.assertEqual(len(hits), 3)
        self.assertTrue(all(hit.name in SKILLS for hit in hits))

        bm25_hits = retrieve_bm25("put some vase on safe")
        self.assertEqual(len(bm25_hits), 3)
        self.assertIn("simple-pick-place", [hit.name for hit in bm25_hits])

    def test_manual_oracle_labels_known_task_family(self):
        labels = gold_skills_for_game(".alfworld-data/json_2.1.1/valid_unseen/pick_heat_then_place_in_recep-Apple-None-GarbageCan-10/trial_x/game.tw-pddl")
        self.assertIn("execute-heat-place", labels)

    def test_light_skills_use_the_supported_action(self):
        self.assertIn("use <desklamp>", SKILLS["light-inspection-sequence"].procedure[1])
        self.assertNotIn("toggle-light", SKILLS)

    def test_frozen_suite_has_thirty_balanced_tasks(self):
        self.assertEqual(validate_suites(), [])
        self.assertEqual(len(ALFWORLD_V2_30), 30)
        self.assertEqual(len(set(ALFWORLD_V2_30)), 30)
        self.assertFalse(set(ALFWORLD_V2_30) & set(ALFWORLD_V3_HELDOUT_30))
        self.assertFalse(set(ALFWORLD_V2_30) & set(ALFWORLD_V5_TEST_30))
        self.assertFalse(set(ALFWORLD_V3_HELDOUT_30) & set(ALFWORLD_V5_TEST_30))
        self.assertEqual({family: list(SUITE_FAMILIES["alfworld-v2-30"].values()).count(family) for family in set(SUITE_FAMILIES["alfworld-v2-30"].values())}, {
            "heat_then_place": 5, "clean_then_place": 5, "cool_then_place": 5,
            "two_object_place": 5, "light_inspection": 5, "simple_pick_place": 5,
        })

    @unittest.skipIf(action_result is None, "ALFWorld is installed only in .venv/alfworld-native")
    def test_nothing_happens_is_an_environment_rejection(self):
        result = action_result(["Nothing happens."], [0], [False], {"won": [False]})
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    @unittest.skipIf(action_result is None, "ALFWorld is installed only in .venv/alfworld-native")
    def test_agent_prompt_uses_desk_lamp(self):
        from alfworld_agent import AGENT_PROTOCOL_VERSION, SYSTEM_PROMPT, routing_query

        self.assertEqual(AGENT_PROTOCOL_VERSION, "v5-goal-only-router")
        self.assertIn("use <desklamp>", SYSTEM_PROMPT)
        self.assertIn("Never use put", SYSTEM_PROMPT)
        observation = "You are in a kitchen with many objects.\nYour task is to: put some vase on safe."
        self.assertEqual(routing_query(observation), "put some vase on safe.")

        from alfworld_agent import select_skills
        selection = select_skills(
            "bm25_body_retrieval",
            "Your task is to: put some vase on safe.",
            ".alfworld-data/json_2.1.1/valid_unseen/pick_and_place_simple-Vase-None-Safe-1/trial_x/game.tw-pddl",
        )
        self.assertEqual(selection.retriever, BM25_RETRIEVER_NAME)
        self.assertIn("simple-pick-place", selection.names)

    @unittest.skipIf(completed_episodes is None, "ALFWorld is installed only in .venv/alfworld-native")
    def test_resume_finds_existing_episode(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            path.write_text('{"run_id":"v2","task_index":2,"condition":"oracle_skill","repeat":0}\n', encoding="utf-8")
            self.assertEqual(completed_episodes(path, "v2"), {(2, "oracle_skill", 0)})


if __name__ == "__main__":
    unittest.main()
