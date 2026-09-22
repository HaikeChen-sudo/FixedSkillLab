"""Check the v4d incline scope fix without calling ScienceWorld or DeepSeek."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import scienceworld_retrieval_audit
from scienceworld_agent import skill_selection
from scienceworld_skills import V4D_SKILL_OVERRIDES, library_hash, validate_library, versioned_skills
from scienceworld_suites import SCIENCEWORLD_V14D_INCLINE_DEV_1, SUITES, SUITE_VARIATION_SPLITS, validate_suites


class V14DDevelopmentTest(unittest.TestCase):
    def test_v4c_is_frozen_and_only_incline_changes(self):
        self.assertEqual(library_hash("v4c"), "822b7d3937611463a1fb93c11c3be37723cd7b5123e096c448e27608bcf6cbe7")
        self.assertEqual(library_hash("v4d"), "5d16691dd48632b07fc2e176ec3daed70b7e089c59c28e7c434e4e06b3e04d0b")
        self.assertEqual(set(V4D_SKILL_OVERRIDES), {"measure-inclined-plane-angle"})
        old = {item.name: item for item in versioned_skills("v4c")}
        new = {item.name: item for item in versioned_skills("v4d")}
        self.assertEqual({name for name in old if old[name] != new[name]}, set(V4D_SKILL_OVERRIDES))
        incline = new["measure-inclined-plane-angle"]
        self.assertIn("shallowest or steepest", incline.activation_condition)
        self.assertIn("longer time indicates the shallower", incline.procedure[-2])
        self.assertIn("shorter time indicates the steeper", incline.procedure[-2])
        self.assertEqual(validate_library(), [])

    def test_v4d_selection_keeps_v4c_available(self):
        query = "Which of inclined plane B and inclined plane F has the steepest angle?"
        for condition in ("flat_retrieval_v4d", "body_aware_retrieval_v4d"):
            selection = skill_selection(condition, "inclined-plane-determine-angle", query)
            self.assertEqual(selection.library_version, "v4d")
            self.assertEqual(selection.gold_skill_ranks, [1])
        self.assertEqual(skill_selection("oracle_v4d", "inclined-plane-determine-angle").names, ["measure-inclined-plane-angle"])
        self.assertEqual(skill_selection("oracle_v4c", "inclined-plane-determine-angle").library_version, "v4c")
        with self.assertRaises(ValueError):
            skill_selection("oracle_v4d", "boil")

    def test_new_dev_suite_and_offline_audit(self):
        self.assertEqual(validate_suites(), [])
        self.assertEqual(SUITE_VARIATION_SPLITS["scienceworld-v14d-incline-dev-1"], "dev")
        self.assertEqual(SCIENCEWORLD_V14D_INCLINE_DEV_1, (("inclined-plane-determine-angle", 86),))
        self.assertFalse(set(SCIENCEWORLD_V14D_INCLINE_DEV_1) & set(SUITES["scienceworld-v14c-dev-check-4"]))

        class FakeEnv:
            def load(self, task_name, variationIdx, simplificationStr):
                self.variation = variationIdx

            def get_variations_dev(self):
                return [self.variation]

            def reset(self):
                return "", {"taskDesc": "Which of inclined plane B and inclined plane F has the steepest angle?"}

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit.jsonl"
            argv = ["audit", "--suite", "scienceworld-v14d-incline-dev-1", "--v14d", "--output", str(output)]
            with patch("sys.argv", argv), patch.object(scienceworld_retrieval_audit, "make_env", return_value=FakeEnv()):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(scienceworld_retrieval_audit.main(), 0)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["skill_library_version"], "v4d")
        self.assertEqual(rows[0]["flat_gold_rank"], 1)
        self.assertEqual(rows[0]["body_gold_rank"], 1)


if __name__ == "__main__":
    unittest.main()
