"""Checks for the conservative, post-hoc inclined-plane process rule."""

import unittest

from scienceworld_incline_process_audit import inspect, TASK_ID


def act(command, observation="", ok=True):
    return {"tool": "act", "command": command, "result": {"ok": ok, "observation": observation}}


def episode(actions):
    return {"task_id": TASK_ID, "condition": "test", "score": 100, "done": True, "trace": actions}


class InclineProcessAuditTests(unittest.TestCase):
    def test_full_trials_support_the_longer_plane(self):
        row = inspect(episode([
            act("move wood block to inclined plane B"),
            act("activate stopwatch"),
            act("examine inclined plane B", "a wood block at the bottom of the plane"),
            act("examine stopwatch", "The time reads 22 ticks."),
            act("deactivate stopwatch"),
            act("put wood block on inclined plane F"),
            act("activate stopwatch"),
            act("examine inclined plane F", "a wood block approximately 100% down the plane"),
            act("deactivate stopwatch"),
            act("examine stopwatch", "The time reads 25 ticks."),
            act("focus on inclined plane F"),
        ]))
        self.assertTrue(row["two_complete_trials"])
        self.assertTrue(row["distinct_final_times"])
        self.assertTrue(row["choice_supported_by_times"])

    def test_early_or_rejected_observations_do_not_complete_a_trial(self):
        row = inspect(episode([
            act("move wood block to inclined plane B"),
            act("activate stopwatch"),
            act("examine stopwatch", "The time reads 3 ticks."),
            act("examine inclined plane B", "a wood block at the bottom of the plane", ok=False),
            act("deactivate stopwatch"),
            act("focus on inclined plane F"),
        ]))
        self.assertEqual(row["complete_trials"], [])
        self.assertFalse(row["two_complete_trials"])
        self.assertIsNone(row["choice_supported_by_times"])

    def test_equal_full_times_do_not_support_a_choice(self):
        actions = []
        for plane in ("B", "F"):
            actions += [
                act(f"move wood block to inclined plane {plane}"),
                act("activate stopwatch"),
                act(f"examine inclined plane {plane}", "a wood block at the bottom of the plane"),
                act("examine stopwatch", "The time reads 22 ticks."),
                act("deactivate stopwatch"),
            ]
        row = inspect(episode(actions + [act("focus on inclined plane F")]))
        self.assertTrue(row["two_complete_trials"])
        self.assertFalse(row["distinct_final_times"])
        self.assertIsNone(row["choice_supported_by_times"])


if __name__ == "__main__":
    unittest.main()
