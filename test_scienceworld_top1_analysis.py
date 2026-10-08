import copy
import json
import unittest

import scienceworld_top1_analysis as analysis


class Top1AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [json.loads(line) for line in analysis.pilot.RESULTS.read_text().splitlines() if line.strip()]

    def test_frozen_real_data_reconciles(self):
        result = analysis.build_analysis()
        self.assertEqual(result["episodes"], 36)
        self.assertEqual([r["successes"] for r in result["condition_summary"]], [9, 12, 12])
        self.assertEqual({r["task_id"] for r in result["failures"]}, {"find-living-thing:v151"})
        self.assertEqual(sum(r["same_skill_prompt"] for r in result["body_flat_pairs"]), 6)

    def test_missing_duplicate_and_extra_records_rejected(self):
        for rows in (self.rows[:-1], self.rows[:-1] + [self.rows[0]], self.rows + [self.rows[0]]):
            with self.assertRaises(ValueError):
                analysis.analyze(rows)

    def test_trace_mismatch_rejected(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["trace"][-1]["result"]["score"] = -123
        with self.assertRaises(ValueError):
            analysis.analyze(rows)

    def test_cost_includes_failed_episodes_and_zero_success_is_null(self):
        rows = copy.deepcopy(self.rows[:2])
        rows[0].update(success=True, cost_usd=1)
        rows[1].update(success=False, cost_usd=2)
        self.assertEqual(analysis.aggregate(rows)["cost_per_successful_task_usd"], 3)
        rows[0]["success"] = False
        self.assertIsNone(analysis.aggregate(rows)["cost_per_successful_task_usd"])


if __name__ == "__main__":
    unittest.main()
