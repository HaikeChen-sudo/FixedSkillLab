import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scienceworld_content_analysis as analysis


class ContentAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = analysis.read_rows(analysis.content.RESULTS)
        cls.manifest = json.loads(analysis.content.MANIFEST.read_text())
        cls.queries = analysis.content.load_queries(cls.manifest)

    def analyze(self, rows):
        return analysis.content_analysis(rows, self.manifest, self.queries)

    def test_real_results_and_frozen_gate(self):
        result = self.analyze(self.rows)
        self.assertEqual([r["successes"] for r in result["condition_summary"]], [12] * 4)
        self.assertEqual(result["movement_gate"]["qualifying_instances"], 0)
        self.assertFalse(result["movement_gate"]["passed"])
        self.assertEqual(result["initial_observation_matches"], 48)

    def test_missing_duplicate_and_foreign_records_rejected(self):
        for rows in (self.rows[:-1], self.rows[:-1] + [self.rows[0]], self.rows + [self.rows[0]]):
            with self.assertRaises(ValueError):
                self.analyze(rows)
        rows = copy.deepcopy(self.rows)
        rows[0]["run_id"] = "another-run"
        with self.assertRaises(ValueError):
            self.analyze(rows)

    def test_initial_state_prompt_and_counter_drift_rejected(self):
        for key, value in (("initial_observation_sha256", None), ("skill_prompt_sha256", "changed"),
                           ("pickup_command_count", 999), ("input_tokens", -1)):
            rows = copy.deepcopy(self.rows)
            rows[0][key] = value
            with self.assertRaises(ValueError):
                self.analyze(rows)

    def test_gate_requires_joint_reduction_and_no_success_loss(self):
        tasks = self.analyze(self.rows)["task_summary"]
        for r in tasks:
            if r["condition"] == "content_correct":
                r.update(average_tool_calls=0, average_pickup_commands=0)
        self.assertTrue(analysis.movement_gate(tasks)["passed"])
        next(r for r in tasks if r["condition"] == "content_correct")["successes"] = 2
        self.assertFalse(analysis.movement_gate(tasks)["passed"])

    def test_fee_denominator_keeps_failures(self):
        rows = copy.deepcopy(self.rows[:2])
        rows[0].update(success=True, cost_usd=1)
        rows[1].update(success=False, cost_usd=2)
        self.assertEqual(analysis.aggregate(rows)["cost_per_successful_task_usd"], 3)
        rows[0]["success"] = False
        self.assertIsNone(analysis.aggregate(rows)["cost_per_successful_task_usd"])

    def test_offline_audit_distinguishes_unknown_and_equal_initial_states(self):
        with patch.object(analysis.content, "run_episode", side_effect=AssertionError("No API")), \
             patch.object(analysis.content, "make_env", side_effect=AssertionError("No environment")), \
             patch.object(analysis.strong, "strong_retrieve", side_effect=AssertionError("No encoder")):
            result = analysis.build_analysis()
        strong, top1 = result["router_review"]
        self.assertEqual((strong["same_set_pairs"], strong["same_prompt_pairs"]), (15, 12))
        self.assertTrue(all(p["same_initial_observation"] is None for p in strong["pairs"]))
        self.assertEqual(top1["same_prompt_pairs"], 6)
        self.assertTrue(all(p["same_initial_observation"] is True for p in top1["pairs"]))
        for review in (strong, top1):
            self.assertEqual(sum(p["flat_minus_body_tokens"] for p in review["pairs"]),
                             sum(g["flat_minus_body_tokens"] for g in review["token_decomposition"]))

    def test_existing_output_is_never_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis.json"
            with patch.object(analysis, "build_analysis", return_value={
                    "content": {"episodes": 48, "movement_gate": {"passed": False}}}):
                analysis.main(["--output", str(output)])
                analysis.main(["--output", str(output)])
            before = output.read_bytes()
            with patch.object(analysis, "build_analysis", return_value={}), self.assertRaises(SystemExit):
                analysis.main(["--output", str(output)])
            self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
