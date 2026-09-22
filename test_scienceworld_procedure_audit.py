"""Offline checks for the two registered Procedure dev tasks."""

import unittest

from scienceworld_procedure_audit import audit_record, procedure_arms


def act(command, score, observation="", done=False):
    return {
        "tool": "act",
        "command": command,
        "result": {"score": score, "observation": observation, "done": done},
    }


def record(task_id, trace, score, condition="arm"):
    return {"task_id": task_id, "condition": condition, "trace": trace, "score": score}


class ProcedureAuditTests(unittest.TestCase):
    def test_both_pairs_change_only_procedure(self):
        arms = procedure_arms()
        self.assertEqual(len(arms), 2)
        self.assertTrue(all(arm["changed_fields"] == ["procedure"] for arm in arms))
        self.assertTrue(all(arm["p0_sha256"] != arm["p1_sha256"] for arm in arms))

    def test_chemistry_orders_events_and_counts_failed_mix(self):
        row = audit_record(record("chemistry-mix:v016", [
            act("look around", 25),
            act("read recipe", 33, "The recipe reads: chocolate, marshmallow."),
            act("mix chocolate in cup", 33, "No known action matches that input."),
            act("mix glass cup", 50, "The mix produces smores."),
            act("focus on smores", 100, done=True),
        ], 100))
        self.assertTrue(row["environment_success"])
        self.assertTrue(row["events"]["read_mix_focus_order"])
        self.assertEqual(row["events"]["unproductive_mix_attempts"], 1)

    def test_chemistry_rejects_focus_before_mix(self):
        row = audit_record(record("chemistry-mix:v016", [
            act("read recipe", 33, "The recipe reads: chocolate."),
            act("focus on chocolate", 33),
            act("mix cup", 50),
        ], 50))
        self.assertFalse(row["events"]["read_mix_focus_order"])
        self.assertFalse(row["environment_success"])

    def test_incline_separates_early_and_wrong_after_milestone(self):
        task_id = "inclined-plane-determine-angle:v084"
        early = audit_record(record(task_id, [
            act("look around", 10),
            act("focus on inclined plane B", -100, done=True),
        ], -100))
        self.assertEqual(early["events"]["decision"], "premature_focus")

        measured = [
            act("put wood block on inclined plane B", 15),
            act("examine stopwatch", 30, "The time reads 22 ticks."),
            act("move wood block to inclined plane F", 35),
            act("examine stopwatch", 50, "The time reads 25 ticks."),
        ]
        wrong = audit_record(record(task_id, measured + [
            act("focus on inclined plane B", -100, done=True),
        ], -100))
        correct = audit_record(record(task_id, measured + [
            act("focus on inclined plane F", 100, done=True),
        ], 100))
        self.assertEqual(wrong["events"]["decision"], "wrong_after_milestone")
        self.assertEqual(correct["events"]["decision"], "correct_after_milestone")

    def test_incline_requires_score_milestone_even_with_two_readings(self):
        row = audit_record(record("inclined-plane-determine-angle:v084", [
            act("move wood block to inclined plane B", 15),
            act("examine stopwatch", 20, "The time reads 3 ticks."),
            act("move wood block to inclined plane F", 30),
            act("examine stopwatch", 40, "The time reads 3 ticks."),
            act("focus on inclined plane B", -100, done=True),
        ], -100))
        self.assertTrue(row["events"]["two_planes_timed"])
        self.assertEqual(row["events"]["decision"], "premature_focus")


if __name__ == "__main__":
    unittest.main()
