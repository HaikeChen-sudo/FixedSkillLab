import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scienceworld_agent import CONDITIONS, DEFAULT_CONDITIONS, objective_success, repeated_action_limit, run_episode, skill_names, skill_selection
from scienceworld_retrieval import EMBEDDER_NAME, retrieve
from scienceworld_experiment import PILOT_TASKS, completed_episodes, experiment_cases
from scienceworld_skills import GOLD_SKILLS, SKILL_LIST, T_HORIZONTAL_SKILL_NAME, T_STRUCTURE_VERSION, T_VERTICAL_PATHS, V2_SKILL_OVERRIDES, V3_SKILL_OVERRIDES, library_hash, loaded_skill_text, validate_library
from analyze_scienceworld_formal import exact_sign_p_value, paired_statistics, validation_errors
from analyze_scienceworld_t1 import success_interaction
from scienceworld_suites import SCIENCEWORLD_PILOT_6, SCIENCEWORLD_TEST_VARIATIONS, SCIENCEWORLD_T1_T_SHAPED_PILOT_12, SCIENCEWORLD_T2_CONTROLLER_DEV_2, SCIENCEWORLD_V3_HELDOUT_6, SCIENCEWORLD_V4_HELDOUT_6, SCIENCEWORLD_V6_ROUTER_FORMAL_12, SCIENCEWORLD_V10_CONFIRM_12, SCIENCEWORLD_V11B_CONFIRM_18, SCIENCEWORLD_V12_MECHANISM_PILOT_6, SCIENCEWORLD_V13_ORACLE_MECHANISM_PILOT_6, SCIENCEWORLD_V13B_ORACLE_MECHANISM_6, SUITE_VARIATION_SPLITS, validate_suites


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

    def test_v10_confirmation_suite_is_new_and_preregistered(self):
        self.assertEqual(SCIENCEWORLD_V10_CONFIRM_12, (
            ("boil", 25), ("boil", 26), ("melt", 25), ("melt", 26),
            ("freeze", 25), ("freeze", 26),
            ("use-thermometer", 409), ("use-thermometer", 410),
            ("find-living-thing", 229), ("find-living-thing", 230),
            ("find-non-living-thing", 229), ("find-non-living-thing", 230),
        ))
        earlier = (
            set(SCIENCEWORLD_PILOT_6)
            | set(SCIENCEWORLD_V3_HELDOUT_6)
            | set(SCIENCEWORLD_V4_HELDOUT_6)
            | set(SCIENCEWORLD_V6_ROUTER_FORMAL_12)
        )
        self.assertFalse(earlier & set(SCIENCEWORLD_V10_CONFIRM_12))
        self.assertEqual(SUITE_VARIATION_SPLITS["scienceworld-v10-confirm-12"], "test")
        manifest = json.loads(Path("results/scienceworld_v10_confirmation_manifest.json").read_text(encoding="utf-8"))
        cases = [(row["task_name"], row["variation"]) for row in manifest["cases"]]
        self.assertEqual(cases, list(SCIENCEWORLD_V10_CONFIRM_12))
        self.assertTrue(manifest["frozen_before_gold_check"])
        self.assertTrue(manifest["frozen_before_api_evaluation"])
        self.assertEqual(manifest["planned_episodes"], 108)
        gold = [json.loads(line) for line in Path("results/scienceworld_v10_gold_validation.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(row["task_name"], row["variation"]) for row in gold], list(SCIENCEWORLD_V10_CONFIRM_12))
        self.assertTrue(all(row["gold_success"] and row["gold_score"] == 100 for row in gold))
        self.assertLessEqual(max(row["gold_environment_moves"] for row in gold), 400)

    def test_invalid_v11_protocol_is_retained_as_an_audit_record(self):
        manifest = json.loads(Path("results/scienceworld_v11_large_confirmation_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "invalidated_during_preflight")
        self.assertEqual(manifest["api_episodes_collected"], 0)
        self.assertEqual(manifest["replacement_suite"], "scienceworld-v11b-confirm-18")

    def test_v11b_confirmation_suite_is_new_valid_and_preregistered(self):
        self.assertEqual(len(SCIENCEWORLD_V11B_CONFIRM_18), 18)
        self.assertEqual(
            {task: sum(name == task for name, _ in SCIENCEWORLD_V11B_CONFIRM_18) for task in GOLD_SKILLS},
            {task: 3 for task in GOLD_SKILLS},
        )
        earlier = (
            set(SCIENCEWORLD_PILOT_6)
            | set(SCIENCEWORLD_V3_HELDOUT_6)
            | set(SCIENCEWORLD_V4_HELDOUT_6)
            | set(SCIENCEWORLD_V6_ROUTER_FORMAL_12)
            | set(SCIENCEWORLD_V10_CONFIRM_12)
        )
        self.assertFalse(earlier & set(SCIENCEWORLD_V11B_CONFIRM_18))
        self.assertTrue(all(
            variation in SCIENCEWORLD_TEST_VARIATIONS[task]
            for task, variation in SCIENCEWORLD_V11B_CONFIRM_18
        ))
        self.assertEqual(SUITE_VARIATION_SPLITS["scienceworld-v11b-confirm-18"], "test")
        manifest = json.loads(Path("results/scienceworld_v11b_confirmation_manifest.json").read_text(encoding="utf-8"))
        cases = [(row["task_name"], row["variation"]) for row in manifest["cases"]]
        self.assertEqual(cases, list(SCIENCEWORLD_V11B_CONFIRM_18))
        self.assertTrue(manifest["frozen_before_gold_check"])
        self.assertTrue(manifest["frozen_before_retrieval_audit"])
        self.assertTrue(manifest["frozen_before_api_evaluation"])
        self.assertEqual(manifest["planned_conditions"], ["no_skill", "flat_retrieval", "body_aware_retrieval"])
        self.assertEqual(manifest["planned_episodes"], 162)
        audit = [json.loads(line) for line in Path("results/scienceworld_v11b_retrieval_audit.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(row["task_name"], row["variation"]) for row in audit], list(SCIENCEWORLD_V11B_CONFIRM_18))
        self.assertEqual(sum(row["flat_gold_rank"] is not None for row in audit), 12)
        self.assertEqual(sum(row["body_gold_rank"] is not None for row in audit), 15)
        gold = [json.loads(line) for line in Path("results/scienceworld_v11b_gold_validation.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(row["task_name"], row["variation"]) for row in gold], list(SCIENCEWORLD_V11B_CONFIRM_18))
        self.assertTrue(all(row["success"] and row["score"] == 100 for row in gold))
        self.assertLessEqual(max(row["environment_moves"] for row in gold), 400)

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

    def test_formal_v10_data_is_complete_and_immutable(self):
        path = Path("results/formal_scienceworld_v10/scienceworld-v10-confirm-12x3.jsonl")
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        conditions = ("no_skill", "flat_retrieval", "body_aware_retrieval")
        self.assertEqual(validation_errors(records, "scienceworld-v10-confirm-12", conditions, 3), [])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), "d6614857fe39458c0e8f23e04c96d75d15d6b7f9cb90c131f0a391b6cfd9a4e2")

    def test_formal_v11b_data_is_complete_and_immutable(self):
        path = Path("results/formal_scienceworld_v11/scienceworld-v11b-confirm-18x3.jsonl")
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        conditions = ("no_skill", "flat_retrieval", "body_aware_retrieval")
        self.assertEqual(validation_errors(records, "scienceworld-v11b-confirm-18", conditions, 3), [])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), "fb46b8f603d68f9e4baea76de912d68d1edac54299018b3b3bd51b7923177956")

    def test_v12_mechanism_pilot_reuses_six_declared_v11b_cases(self):
        self.assertEqual(SCIENCEWORLD_V12_MECHANISM_PILOT_6, (
            ("boil", 27), ("melt", 27), ("freeze", 27),
            ("use-thermometer", 411), ("find-living-thing", 231),
            ("find-non-living-thing", 231),
        ))
        self.assertTrue(set(SCIENCEWORLD_V12_MECHANISM_PILOT_6) <= set(SCIENCEWORLD_V11B_CONFIRM_18))
        manifest = json.loads(Path("results/scienceworld_v12_mechanism_pilot_manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["frozen_before_api_evaluation"])
        self.assertEqual(manifest["planned_episodes"], 24)

    def test_v12_controls_keep_body_router_selection_and_match_placebo_words(self):
        records = [
            json.loads(line)
            for line in Path("results/formal_scienceworld_v11/scienceworld-v11b-confirm-18x3.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        queries = {
            (row["task_name"], row["variation"]): row["retrieval_query"]
            for row in records
        }
        for task_name, variation in SCIENCEWORLD_V12_MECHANISM_PILOT_6:
            query = queries[(task_name, variation)]
            full = skill_selection("body_aware_retrieval", task_name, query)
            for condition in ("body_metadata_only", "body_placebo"):
                control = skill_selection(condition, task_name, query)
                self.assertEqual(control.names, full.names)
                self.assertEqual(control.retrieved, full.retrieved)
                self.assertEqual(control.gold_skill_ranks, full.gold_skill_ranks)
            full_text = loaded_skill_text(full.names, "v3")
            metadata = loaded_skill_text(full.names, "v3", "metadata_only")
            placebo = loaded_skill_text(full.names, "v3", "placebo")
            self.assertLess(len(metadata.split()), len(full_text.split()))
            self.assertEqual(len(placebo.split()), len(full_text.split()))
            self.assertLess(abs(len(placebo) - len(full_text)) / len(full_text), 0.15)
            self.assertNotEqual(placebo, full_text)

    def test_v13_controls_load_the_same_single_gold_skill(self):
        self.assertEqual(SCIENCEWORLD_V13_ORACLE_MECHANISM_PILOT_6, SCIENCEWORLD_V12_MECHANISM_PILOT_6)
        manifest = json.loads(Path("results/scienceworld_v13_oracle_mechanism_pilot_manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["frozen_before_api_evaluation"])
        self.assertEqual(manifest["conditions"], [
            "no_skill", "oracle_v3_full", "oracle_v3_metadata", "oracle_v3_placebo",
        ])
        self.assertEqual(manifest["planned_episodes"], 24)
        for task_name in GOLD_SKILLS:
            selections = [
                skill_selection(condition, task_name)
                for condition in ("oracle_v3_full", "oracle_v3_metadata", "oracle_v3_placebo")
            ]
            self.assertTrue(all(item.names == [GOLD_SKILLS[task_name]] for item in selections))
            self.assertTrue(all(item.retrieved == [] and item.retriever is None for item in selections))
            self.assertTrue(all(item.library_version == "v3" for item in selections))
            full = loaded_skill_text(selections[0].names, "v3", "full")
            metadata = loaded_skill_text(selections[0].names, "v3", "metadata_only")
            placebo = loaded_skill_text(selections[0].names, "v3", "placebo")
            self.assertLess(len(metadata.split()), len(full.split()))
            self.assertEqual(len(placebo.split()), len(full.split()))
            self.assertLess(abs(len(placebo) - len(full)) / len(full), 0.15)

    def test_v13_episode_records_the_requested_gold_render_mode(self):
        class FakeEnv:
            def load(self, *_args, **_kwargs):
                pass

            def reset(self):
                return "room", {"taskDesc": "Your task is to boil gallium.", "score": 0, "moves": 0}

            def close(self):
                pass

        class StopClient:
            def __init__(self, *_args, **_kwargs):
                pass

            def respond(self, _messages):
                return {"role": "assistant", "content": "stop"}

            def metrics(self):
                return {"input_tokens": 0, "output_tokens": 0, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0}

        expected = {
            "oracle_v3_full": "full",
            "oracle_v3_metadata": "metadata_only",
            "oracle_v3_placebo": "placebo",
        }
        records = {}
        with patch("scienceworld_agent.make_env", return_value=FakeEnv()), patch("scienceworld_agent.DeepSeekChatClient", StopClient):
            for condition, mode in expected.items():
                records[condition] = run_episode("test", 0, "boil", 27, "easy", 1, condition)
                self.assertEqual(records[condition]["skill_render_mode"], mode)
                self.assertEqual(records[condition]["skills_loaded"], ["boil-substance"])
        self.assertEqual(len({row["skill_prompt_sha256"] for row in records.values()}), 3)

    def test_v13b_targets_state_change_cases_and_is_preregistered(self):
        self.assertEqual(SCIENCEWORLD_V13B_ORACLE_MECHANISM_6, (
            ("boil", 27), ("boil", 28), ("boil", 29),
            ("freeze", 27), ("freeze", 28), ("freeze", 29),
        ))
        self.assertTrue(set(SCIENCEWORLD_V13B_ORACLE_MECHANISM_6) <= set(SCIENCEWORLD_V11B_CONFIRM_18))
        self.assertEqual(SUITE_VARIATION_SPLITS["scienceworld-v13b-oracle-mechanism-6"], "test")
        manifest = json.loads(Path("results/scienceworld_v13b_oracle_mechanism_manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["frozen_before_api_evaluation"])
        self.assertEqual(manifest["conditions"], [
            "oracle_v3_full", "oracle_v3_metadata", "oracle_v3_placebo",
        ])
        self.assertEqual(manifest["repeats"], 3)
        self.assertEqual(manifest["planned_episodes"], 54)

    def test_formal_v13b_data_is_complete_immutable_and_paired(self):
        path = Path("results/formal_scienceworld_v13b/scienceworld-v13b-oracle-mechanism-6x3.jsonl")
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        conditions = ("oracle_v3_full", "oracle_v3_metadata", "oracle_v3_placebo")
        self.assertEqual(validation_errors(records, "scienceworld-v13b-oracle-mechanism-6", conditions, 3), [])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), "5e671e5c04d2e92a0041f8e5b74b0a0e89bfbaefd66c13a79314e904798a6692")
        paired = {}
        for row in records:
            paired.setdefault((row["task_name"], row["variation"], row["repeat"]), []).append(row)
        self.assertTrue(all(len(rows) == 3 for rows in paired.values()))
        self.assertTrue(all(len({tuple(row["skills_loaded"]) for row in rows}) == 1 for rows in paired.values()))

    def test_t1_pilot_is_a_frozen_reuse_mechanism_suite(self):
        self.assertEqual(SCIENCEWORLD_T1_T_SHAPED_PILOT_12, SCIENCEWORLD_V10_CONFIRM_12)
        self.assertEqual(SUITE_VARIATION_SPLITS["scienceworld-t1-t-shaped-pilot-12"], "test")
        manifest = json.loads(Path("results/scienceworld_t1_t_shaped_pilot_manifest.json").read_text(encoding="utf-8"))
        cases = [(row["task_name"], row["variation"]) for row in manifest["cases"]]
        self.assertEqual(cases, list(SCIENCEWORLD_T1_T_SHAPED_PILOT_12))
        self.assertEqual(manifest["source_suite"], "scienceworld-v10-confirm-12")
        self.assertEqual(manifest["conditions"], ["no_skill", "t_horizontal", "t_vertical", "t_full"])
        self.assertTrue(manifest["frozen_before_api_evaluation"])
        self.assertEqual(manifest["api_episodes_collected"], 0)
        self.assertEqual(manifest["planned_episodes"], 48)
        audit = [
            json.loads(line)
            for line in Path(manifest["offline_prompt_audit"]).read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(audit), 48)
        self.assertEqual({row["condition"] for row in audit}, set(manifest["conditions"]))
        self.assertEqual({(row["task_name"], row["variation"]) for row in audit}, set(SCIENCEWORLD_T1_T_SHAPED_PILOT_12))

    def test_t1_conditions_form_the_declared_two_by_two(self):
        self.assertEqual(T_STRUCTURE_VERSION, "t1")
        self.assertEqual(set(T_VERTICAL_PATHS), set(GOLD_SKILLS))
        horizontal = skill_selection("t_horizontal", "boil")
        vertical = skill_selection("t_vertical", "boil")
        full = skill_selection("t_full", "boil")
        self.assertEqual(horizontal.names, [T_HORIZONTAL_SKILL_NAME])
        self.assertEqual(vertical.names, ["boil-substance"])
        self.assertEqual(full.names, [T_HORIZONTAL_SKILL_NAME, "boil-substance"])
        self.assertTrue(all(item.library_version == "t1" for item in (horizontal, vertical, full)))
        self.assertTrue(all(item.retrieved == [] and item.retriever is None for item in (horizontal, vertical, full)))
        self.assertEqual(T_VERTICAL_PATHS["boil"], ("state-change", "heating", "boil"))
        rendered = loaded_skill_text(full.names, "t1")
        self.assertLess(rendered.index(T_HORIZONTAL_SKILL_NAME), rendered.index("boil-substance"))
        self.assertNotEqual(library_hash("t1"), library_hash("v3"))
        self.assertEqual(library_hash("t1"), "250ff29c27e3f00bbea88e891a7b6fa5ca4b3fabc2865c8e4911a22d3602aba3")

    def test_t1_episode_records_loaded_layers_and_prompt_size(self):
        class FakeEnv:
            def load(self, *_args, **_kwargs):
                pass

            def reset(self):
                return "room", {"taskDesc": "Your task is to boil gallium.", "score": 0, "moves": 0}

            def close(self):
                pass

        class StopClient:
            def __init__(self, *_args, **_kwargs):
                pass

            def respond(self, _messages):
                return {"role": "assistant", "content": "stop"}

            def metrics(self):
                return {"input_tokens": 0, "output_tokens": 0, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0}

        records = {}
        with patch("scienceworld_agent.make_env", return_value=FakeEnv()), patch("scienceworld_agent.DeepSeekChatClient", StopClient):
            for condition in ("no_skill", "t_horizontal", "t_vertical", "t_full"):
                records[condition] = run_episode("test", 0, "boil", 25, "easy", 1, condition)
        self.assertFalse(records["no_skill"]["horizontal_layer_loaded"])
        self.assertFalse(records["no_skill"]["vertical_layer_loaded"])
        self.assertTrue(records["t_horizontal"]["horizontal_layer_loaded"])
        self.assertFalse(records["t_horizontal"]["vertical_layer_loaded"])
        self.assertFalse(records["t_vertical"]["horizontal_layer_loaded"])
        self.assertTrue(records["t_vertical"]["vertical_layer_loaded"])
        self.assertEqual(records["t_vertical"]["vertical_path"], ["state-change", "heating", "boil"])
        self.assertEqual(records["t_full"]["skills_loaded"], [T_HORIZONTAL_SKILL_NAME, "boil-substance"])
        self.assertEqual(records["t_full"]["structure_version"], "t1")
        self.assertGreater(records["t_full"]["skill_prompt_words"], records["t_vertical"]["skill_prompt_words"])
        self.assertEqual(len({records[name]["skill_prompt_sha256"] for name in ("t_horizontal", "t_vertical", "t_full")}), 3)

    def test_t1_success_interaction_uses_the_preregistered_formula(self):
        rows = [
            {"condition": "no_skill", "success": False},
            {"condition": "t_horizontal", "success": False},
            {"condition": "t_vertical", "success": False},
            {"condition": "t_full", "success": True},
        ]
        result = success_interaction(rows)
        self.assertEqual(result["interaction"], 1.0)
        self.assertEqual(result["interaction_percentage_points"], 100.0)

    def test_formal_t1_data_is_complete_and_immutable(self):
        path = Path("results/formal_scienceworld_t1/scienceworld-t1-t-shaped-pilot-12x1.jsonl")
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        conditions = ("no_skill", "t_horizontal", "t_vertical", "t_full")
        self.assertEqual(validation_errors(records, "scienceworld-t1-t-shaped-pilot-12", conditions, 1), [])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), "4a288383750d1625bf538629c498af9fd0c07e34c4bd8b95d212dc935f2fa7ee")

    def test_t2_controller_development_protocol_is_explicitly_post_t1(self):
        self.assertEqual(SCIENCEWORLD_T2_CONTROLLER_DEV_2, (("melt", 25), ("freeze", 26)))
        self.assertTrue(set(SCIENCEWORLD_T2_CONTROLLER_DEV_2) <= set(SCIENCEWORLD_T1_T_SHAPED_PILOT_12))
        manifest = json.loads(Path("results/scienceworld_t2_controller_dev_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["analysis_scope"].split(".")[0], "Development only")
        self.assertTrue(manifest["frozen_before_api_evaluation"])
        self.assertEqual(manifest["planned_episodes"], 24)
        self.assertEqual(manifest["conditions"], ["no_skill", "t2_horizontal", "t2_vertical", "t2_full"])
        self.assertEqual(skill_selection("t2_horizontal", "melt").names, [T_HORIZONTAL_SKILL_NAME])
        self.assertEqual(skill_selection("t2_vertical", "melt").names, ["melt-substance"])
        self.assertEqual(skill_selection("t2_full", "melt").names, [T_HORIZONTAL_SKILL_NAME, "melt-substance"])

    def test_t2_progress_controller_blocks_only_repeated_no_progress_actions(self):
        self.assertEqual(repeated_action_limit("wait1"), 8)
        self.assertEqual(repeated_action_limit(" WAIT "), 2)
        self.assertEqual(repeated_action_limit("examine cup"), 3)

        class FakeEnv:
            def __init__(self):
                self.commands = []

            def load(self, *_args, **_kwargs):
                pass

            def reset(self):
                return "room", {"taskDesc": "Your task is to melt mercury.", "score": 0, "moves": 0}

            def step(self, command):
                self.commands.append(command)
                return "no progress", 0, False, {"score": 0, "moves": len(self.commands)}

            def close(self):
                pass

        class RepeatingClient:
            def __init__(self, *_args, **_kwargs):
                self.turn = 0

            def respond(self, _messages):
                self.turn += 1
                return {"role": "assistant", "content": None, "tool_calls": [
                    {"id": f"call-{self.turn}", "type": "function", "function": {"name": "act", "arguments": '{"command":"wait1"}'}},
                ]}

            def metrics(self):
                return {"input_tokens": 0, "output_tokens": 0, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0}

        env = FakeEnv()
        with patch("scienceworld_agent.make_env", return_value=env), patch("scienceworld_agent.DeepSeekChatClient", RepeatingClient):
            record = run_episode("test", 0, "melt", 25, "easy", 10, "t2_horizontal")
        self.assertEqual(env.commands, ["wait1"] * 8)
        self.assertEqual(record["environment_actions"], 8)
        self.assertEqual(record["controller_interventions"], 2)
        self.assertEqual(record["horizontal_controller_version"], "repeated-action-guard-v1")
        self.assertEqual(record["structure_version"], "t2")
        self.assertTrue(all(not row["result"]["ok"] for row in record["trace"][-2:]))

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

    def test_paired_statistics_can_compare_retrieval_conditions_directly(self):
        tasks = (("boil", 27),)
        records = [
            {"task_name": "boil", "variation": 27, "condition": "flat_retrieval", "repeat": 0, "success": False, "total_tokens": 20},
            {"task_name": "boil", "variation": 27, "condition": "body_aware_retrieval", "repeat": 0, "success": True, "total_tokens": 10},
        ]
        result = paired_statistics(records, tasks, ("flat_retrieval", "body_aware_retrieval"), 1, iterations=10)
        self.assertEqual(result[0]["baseline"], "flat_retrieval")
        self.assertEqual(result[0]["condition"], "body_aware_retrieval")
        self.assertEqual(result[0]["success_rate_difference"], 1)
        self.assertEqual(result[0]["average_total_tokens_difference"], -10)

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
