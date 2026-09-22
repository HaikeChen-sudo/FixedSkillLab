"""v14c keeps old results reproducible and can be checked without an API."""

import io
import json
import tempfile
import unittest
from dataclasses import replace
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import scienceworld_retrieval_audit
from scienceworld_agent import skill_selection
from scienceworld_skills import V4C_SKILL_OVERRIDES, library_hash, versioned_skills
from scienceworld_suites import SCIENCEWORLD_V14C_DEV_CHECK_4, SUITES, SUITE_VARIATION_SPLITS, validate_suites


class V14CDevelopmentTest(unittest.TestCase):
    def test_v4b_is_frozen_and_v4c_changes_only_two_skills(self):
        self.assertEqual(library_hash("v4b"), "37faee802461ff8d76d7284dc832e4f71f41503fb1b044b9aa64c9ba23b4ffd4")
        self.assertEqual(library_hash("v4c"), "822b7d3937611463a1fb93c11c3be37723cd7b5123e096c448e27608bcf6cbe7")
        self.assertEqual(set(V4C_SKILL_OVERRIDES), {"power-component-circuit", "measure-inclined-plane-angle"})
        old = {item.name: item for item in versioned_skills("v4b")}
        new = {item.name: item for item in versioned_skills("v4c")}
        self.assertEqual({name for name in old if old[name] != new[name]}, set(V4C_SKILL_OVERRIDES))
        self.assertEqual(new["power-component-circuit"], replace(old["power-component-circuit"], description=new["power-component-circuit"].description))
        self.assertEqual(new["measure-inclined-plane-angle"], replace(old["measure-inclined-plane-angle"], procedure=new["measure-inclined-plane-angle"].procedure))

    def test_old_dev_power_query_now_retrieves_gold(self):
        query = "Task Description:\nYour task is to turn on the blue light bulb. First, focus on the blue light bulb. Then, create an electrical circuit that powers it on."
        old = skill_selection("body_aware_retrieval", "power-component", query)
        new = skill_selection("body_aware_retrieval_v4c", "power-component", query)
        self.assertIsNone(old.gold_skill_ranks[0])
        self.assertEqual(new.gold_skill_ranks, [1])
        self.assertEqual(new.library_version, "v4c")
        self.assertEqual(skill_selection("flat_retrieval_v4c", "power-component", query).library_version, "v4c")
        self.assertEqual(skill_selection("oracle_v4", "power-component").library_version, "v4b")
        self.assertEqual(skill_selection("oracle_v4c", "power-component").library_version, "v4c")
        with self.assertRaises(ValueError):
            skill_selection("body_aware_retrieval_v4c", "boil", query)

    def test_new_dev_suite_is_disjoint_and_audits_v4c(self):
        self.assertEqual(validate_suites(), [])
        self.assertEqual(SUITE_VARIATION_SPLITS["scienceworld-v14c-dev-check-4"], "dev")
        self.assertFalse(set(SCIENCEWORLD_V14C_DEV_CHECK_4) & set(SUITES["scienceworld-v14-dev-4"]))

        class FakeEnv:
            def load(self, task_name, variationIdx, simplificationStr):
                self.variation = variationIdx
                self.task_name = task_name

            def get_variations_dev(self):
                return [self.variation]

            def reset(self):
                return "", {"taskDesc": f"Your task is to {self.task_name.replace('-', ' ')}."}

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit.jsonl"
            argv = ["audit", "--suite", "scienceworld-v14c-dev-check-4", "--v14c", "--output", str(output)]
            with patch("sys.argv", argv), patch.object(scienceworld_retrieval_audit, "make_env", return_value=FakeEnv()):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(scienceworld_retrieval_audit.main(), 0)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 4)
        self.assertEqual({row["skill_library_version"] for row in rows}, {"v4c"})


if __name__ == "__main__":
    unittest.main()
