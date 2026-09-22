"""Offline safeguards for the opt-in Procedure holdout."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import scienceworld_procedure_holdout as holdout


class SplitEnv:
    def __init__(self, omit=None):
        self.omit = omit
        self.task_name = None
        self.closed = False

    def load(self, task_name, **_kwargs):
        self.task_name = task_name

    def get_variations_test(self):
        variations = {variation for name, variation in holdout.CASES if name == self.task_name}
        return sorted(variations - ({self.omit} if self.omit is not None else set()))

    def close(self):
        self.closed = True


class HoldoutTests(unittest.TestCase):
    def test_preview_is_read_only_and_has_36_paired_episodes(self):
        output = StringIO()
        with patch("sys.argv", ["scienceworld_procedure_holdout.py"]), patch.object(
            holdout, "verify_test_split", side_effect=AssertionError("preview touched environment")
        ), patch.object(holdout.pilot, "run_arm", side_effect=AssertionError("preview called model")), redirect_stdout(output):
            self.assertEqual(holdout.main(), 0)
        preview = json.loads(output.getvalue())
        self.assertEqual(preview["api_calls"], 0)
        self.assertEqual(len(preview["episodes"]), 36)
        keys = {(row["task_name"], row["variation"], row["repeat"]) for row in preview["episodes"]}
        self.assertEqual(len(keys), 18)
        for key in keys:
            self.assertEqual({row["condition"] for row in preview["episodes"] if (
                row["task_name"], row["variation"], row["repeat"]
            ) == key}, set(holdout.pilot.ARMS))

    def test_split_mismatch_stops_before_model_call(self):
        env = SplitEnv(omit=129)
        with TemporaryDirectory() as directory:
            results = Path(directory) / "results.jsonl"
            with patch("sys.argv", [
                "scienceworld_procedure_holdout.py", "--execute", "--run-id", "test-split-mismatch",
                "--results", str(results),
            ]), patch.object(holdout, "make_env", return_value=env), patch.object(
                holdout.pilot, "run_arm", side_effect=AssertionError("model called before split check")
            ):
                with self.assertRaisesRegex(ValueError, "not in official test split"):
                    holdout.main()
            self.assertTrue(env.closed)
            self.assertFalse(results.exists())

    def test_resume_rejects_foreign_manifest(self):
        preview = StringIO()
        with patch("sys.argv", ["scienceworld_procedure_holdout.py"]), redirect_stdout(preview):
            holdout.main()
        row = json.loads(preview.getvalue())["episodes"][0]
        record = {
            "run_id": "test-foreign", "task_name": row["task_name"], "variation": row["variation"],
            "repeat": row["repeat"], "condition": row["condition"], "model": holdout.pilot.MODEL,
            "temperature": holdout.pilot.TEMPERATURE, "max_steps": holdout.MAX_STEPS,
            "suite": holdout.SUITE, "order_seed": holdout.ORDER_SEED,
            "skill_prompt_sha256": row["skill_prompt_sha256"], "variation_split": "test",
            "manifest_sha256": "foreign", "cost_usd": 0.0,
        }
        with TemporaryDirectory() as directory:
            results = Path(directory) / "results.jsonl"
            results.write_text(json.dumps(record) + "\n", encoding="utf-8")
            with patch("sys.argv", [
                "scienceworld_procedure_holdout.py", "--execute", "--resume",
                "--run-id", "test-foreign", "--results", str(results),
            ]), patch.object(holdout, "verify_test_split", side_effect=AssertionError("split check happened")):
                with self.assertRaisesRegex(ValueError, "incompatible holdout record"):
                    holdout.main()


if __name__ == "__main__":
    unittest.main()
