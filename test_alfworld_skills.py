import unittest

from alfworld_gold_skills import gold_skills_for_game
from alfworld_retrieval import BM25_RETRIEVER_NAME, retrieve, retrieve_bm25, routing_query
from alfworld_skills import SKILL_LIST, SKILLS, V6_SKILL_OVERRIDES, V7_SKILL_OVERRIDES, library_hash, loaded_skill_text, validate_library
from alfworld_suites import ALFWORLD_V2_30, ALFWORLD_V3_HELDOUT_30, ALFWORLD_V5_TEST_30, ALFWORLD_V6_DEV_20, ALFWORLD_V7_TARGETED_TEST_10, ALFWORLD_V8_CONFIRM_20, SUITE_FAMILIES, SUITE_SPLITS, validate_suites

try:
    from alfworld_agent import action_result
    from alfworld_experiment import completed_episodes, resolve_split
except ModuleNotFoundError:
    action_result = None
    completed_episodes = None
    resolve_split = None


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
        self.assertEqual(routing_query("Room description.\nYour task is to: put two pillow in sofa."), "put two pillow in sofa.")

    def test_manual_oracle_labels_known_task_family(self):
        labels = gold_skills_for_game(".alfworld-data/json_2.1.1/valid_unseen/pick_heat_then_place_in_recep-Apple-None-GarbageCan-10/trial_x/game.tw-pddl")
        self.assertIn("execute-heat-place", labels)

    def test_light_skills_use_the_supported_action(self):
        self.assertIn("use <desklamp>", SKILLS["light-inspection-sequence"].procedure[1])
        self.assertNotIn("toggle-light", SKILLS)

    def test_v6_overrides_only_the_two_target_skills(self):
        self.assertEqual(set(V6_SKILL_OVERRIDES), {"execute-heat-place", "two-object-placement"})
        self.assertEqual(library_hash("v5"), "d6cb0489ae5dfc6135d868c95fdcca6828b83355ae7a6a19fb3232ff6ccd631b")
        self.assertEqual(library_hash("v6"), "865bab4ce6da8ff6414f6e3a3ecdef02631442aee5dc40a379c936ffa2ec54b5")
        self.assertNotEqual(library_hash("v5"), library_hash("v6"))
        two_object = loaded_skill_text(["two-object-placement"], "v6")
        self.assertIn("different numbered instance", two_object)
        self.assertIn("never take or move an object with another noun", two_object)
        heat = loaded_skill_text(["execute-heat-place"], "v6")
        self.assertIn("take the heated target back", heat)

    def test_v7_fixes_only_the_heat_workflow(self):
        self.assertEqual(set(V7_SKILL_OVERRIDES), {"execute-heat-place"})
        self.assertEqual(library_hash("v7"), "070ba8b35088c2f04bc13db77ae82e55a8074428a56f5b6fc86d85be478a82dd")
        self.assertNotEqual(library_hash("v6"), library_hash("v7"))
        heat = loaded_skill_text(["execute-heat-place"], "v7")
        self.assertIn("heat <target> with <microwave>", heat)
        self.assertIn("cup and mug as different objects", heat)
        self.assertNotIn("move the target inside", heat)
        self.assertEqual(
            loaded_skill_text(["two-object-placement"], "v6"),
            loaded_skill_text(["two-object-placement"], "v7"),
        )

    def test_frozen_suite_has_thirty_balanced_tasks(self):
        self.assertEqual(validate_suites(), [])
        self.assertEqual(len(ALFWORLD_V2_30), 30)
        self.assertEqual(len(set(ALFWORLD_V2_30)), 30)
        self.assertFalse(set(ALFWORLD_V2_30) & set(ALFWORLD_V3_HELDOUT_30))
        self.assertFalse(set(ALFWORLD_V2_30) & set(ALFWORLD_V5_TEST_30))
        self.assertFalse(set(ALFWORLD_V3_HELDOUT_30) & set(ALFWORLD_V5_TEST_30))
        self.assertEqual(len(ALFWORLD_V6_DEV_20), 20)
        self.assertEqual(ALFWORLD_V6_DEV_20[10:], (1, 16, 35, 41, 43, 66, 75, 82, 83, 91))
        self.assertEqual(SUITE_SPLITS["alfworld-v6-dev-20"], "valid_seen")
        self.assertEqual(list(SUITE_FAMILIES["alfworld-v6-dev-20"].values()).count("heat_then_place"), 10)
        self.assertEqual(list(SUITE_FAMILIES["alfworld-v6-dev-20"].values()).count("two_object_place"), 10)
        self.assertEqual(ALFWORLD_V7_TARGETED_TEST_10, (79, 80, 101, 102, 103, 113, 114, 115, 120, 121))
        self.assertEqual(SUITE_SPLITS["alfworld-v7-targeted-test-10"], "valid_unseen")
        self.assertEqual(list(SUITE_FAMILIES["alfworld-v7-targeted-test-10"].values()).count("heat_then_place"), 8)
        self.assertEqual(list(SUITE_FAMILIES["alfworld-v7-targeted-test-10"].values()).count("two_object_place"), 2)
        self.assertEqual(len(ALFWORLD_V8_CONFIRM_20), 20)
        self.assertFalse(set(ALFWORLD_V6_DEV_20) & set(ALFWORLD_V8_CONFIRM_20))
        self.assertEqual(SUITE_SPLITS["alfworld-v8-confirm-20"], "valid_seen")
        self.assertEqual(list(SUITE_FAMILIES["alfworld-v8-confirm-20"].values()).count("heat_then_place"), 6)
        self.assertEqual(list(SUITE_FAMILIES["alfworld-v8-confirm-20"].values()).count("two_object_place"), 14)
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
        from alfworld_agent import AGENT_PROTOCOL_VERSION, SYSTEM_PROMPT

        self.assertEqual(AGENT_PROTOCOL_VERSION, "v7-versioned-oracle")
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

        v5 = select_skills(
            "oracle_v5",
            "heat an apple and put it in garbagecan.",
            ".alfworld-data/json_2.1.1/valid_seen/pick_heat_then_place_in_recep-Apple-None-GarbageCan-1/trial_x/game.tw-pddl",
        )
        v6 = select_skills(
            "oracle_v6",
            "heat an apple and put it in garbagecan.",
            ".alfworld-data/json_2.1.1/valid_seen/pick_heat_then_place_in_recep-Apple-None-GarbageCan-1/trial_x/game.tw-pddl",
        )
        v7 = select_skills(
            "oracle_v7",
            "heat an apple and put it in garbagecan.",
            ".alfworld-data/json_2.1.1/valid_seen/pick_heat_then_place_in_recep-Apple-None-GarbageCan-1/trial_x/game.tw-pddl",
        )
        self.assertEqual(v5.names, v6.names)
        self.assertEqual(v6.names, v7.names)
        self.assertEqual((v5.library_version, v6.library_version, v7.library_version), ("v5", "v6", "v7"))

    @unittest.skipIf(completed_episodes is None, "ALFWorld is installed only in .venv/alfworld-native")
    def test_resume_finds_existing_episode(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            path.write_text('{"run_id":"v2","task_index":2,"condition":"oracle_skill","repeat":0}\n', encoding="utf-8")
            self.assertEqual(completed_episodes(path, "v2"), {(2, "oracle_skill", 0)})

    @unittest.skipIf(resolve_split is None, "ALFWorld is installed only in .venv/alfworld-native")
    def test_v6_suite_chooses_valid_seen(self):
        self.assertEqual(resolve_split("alfworld-v6-dev-20", None), "valid_seen")
        self.assertEqual(resolve_split("alfworld-v7-targeted-test-10", None), "valid_unseen")
        self.assertEqual(resolve_split("alfworld-v8-confirm-20", None), "valid_seen")
        with self.assertRaises(ValueError):
            resolve_split("alfworld-v6-dev-20", "valid_unseen")


if __name__ == "__main__":
    unittest.main()
