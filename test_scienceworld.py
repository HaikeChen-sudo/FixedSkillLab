import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scienceworld_agent import DEFAULT_CONDITIONS, objective_success, skill_names, skill_selection
from scienceworld_experiment import PILOT_TASKS, completed_episodes
from scienceworld_skills import GOLD_SKILLS, SKILL_LIST, V2_SKILL_OVERRIDES, library_hash, loaded_skill_text, validate_library


class ScienceWorldTests(unittest.TestCase):
    def test_pilot_has_six_fixed_oracle_skills(self):
        self.assertEqual(validate_library(), [])
        self.assertEqual(len(PILOT_TASKS), 6)
        self.assertEqual(set(PILOT_TASKS), set(GOLD_SKILLS))
        self.assertEqual(len(SKILL_LIST), 6)

    def test_conditions_change_only_loaded_skill(self):
        self.assertEqual(skill_names("no_skill", "boil"), [])
        self.assertEqual(skill_names("oracle_skill", "boil"), ["boil-substance"])
        self.assertEqual(skill_selection("oracle_v2", "boil"), (["boil-substance"], "v2"))
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


if __name__ == "__main__":
    unittest.main()
