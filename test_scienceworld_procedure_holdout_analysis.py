"""Offline checks for the frozen holdout summaries."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scienceworld_procedure_holdout import CASES, REPEATS, SUITE, verify_manifest
from scienceworld_procedure_holdout_analysis import analyze, load_complete_run


def fake_record(name, variation, repeat, arm):
    is_chemistry_p1 = name == "chemistry-mix" and arm == "procedure_p1"
    trace = [
        {"tool": "act", "command": "read recipe", "result": {"ok": True, "observation": "The recipe reads: mix ingredients", "score": 20}},
        {"tool": "act", "command": "mix bowl", "result": {"ok": True, "observation": "Mixed", "score": 50}},
        {"tool": "act", "command": "focus on product", "result": {"ok": True, "observation": "Done", "score": 100, "done": True}},
    ] if is_chemistry_p1 else []
    return {
        "run_id": "holdout-test", "task_name": name, "variation": variation,
        "task_id": f"{name}:v{variation:03d}", "repeat": repeat, "condition": arm,
        "suite": SUITE, "manifest_sha256": verify_manifest(), "trace": trace,
        "success": True, "score": 100, "done": True,
        "input_tokens": 100, "output_tokens": 10, "total_tokens": 110,
        "latency_ms": 1000, "cost_usd": 0.001, "tool_calls": 3,
    }


class HoldoutAnalysisTests(unittest.TestCase):
    def test_complete_run_and_family_specific_process(self):
        records = [fake_record(name, variation, repeat, arm) for name, variation in CASES
                   for repeat in range(REPEATS) for arm in ("procedure_p0", "procedure_p1")]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
            result = analyze(load_complete_run(path, "holdout-test"))
        self.assertEqual(len(result["paired_by_variation"]), 6)
        summaries = {(row["task_name"], row["condition"]): row for row in result["family_condition_summaries"]}
        self.assertEqual(summaries[("chemistry-mix", "procedure_p1")]["procedure_complete_count"], 9)
        self.assertEqual(summaries[("chemistry-mix", "procedure_p0")]["procedure_complete_count"], 0)
        self.assertEqual(summaries[("inclined-plane-determine-angle", "procedure_p1")]["choice_unassessable_count"], 9)
        self.assertTrue(all(row["success_difference_p1_minus_p0"] == 0 for row in result["paired_by_variation"]))

    def test_missing_episode_is_not_silently_summarized(self):
        name, variation = CASES[0]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            path.write_text(json.dumps(fake_record(name, variation, 0, "procedure_p0")) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "holdout incomplete"):
                load_complete_run(path, "holdout-test")


if __name__ == "__main__":
    unittest.main()
