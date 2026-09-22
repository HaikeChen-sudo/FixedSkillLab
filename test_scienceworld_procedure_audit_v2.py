"""Synthetic checks for the post-holdout process auditor."""

import unittest

from scienceworld_procedure_audit_v2 import chemistry_process, incline_process


def act(command, observation=""):
    return {"tool": "act", "command": command, "result": {"ok": True, "observation": observation}}


def trial(object_name, plane, ticks):
    return [
        act(f"move {object_name} to inclined plane {plane}"),
        act("activate stopwatch"),
        act(f"examine inclined plane {plane}", f"a {object_name} at the bottom of the plane"),
        act("examine stopwatch", f"The time reads {ticks} ticks."),
        act("deactivate stopwatch"),
    ]


class ProcedureAuditV2Tests(unittest.TestCase):
    def test_chemistry_accepts_disambiguated_read_and_mix(self):
        record = {"trace": [
            act("read recipe", "Ambiguous request"),
            act("1", "The recipe reads: mix two ingredients"),
            act("mix bowl", "Ambiguous request"),
            act("2", "Two ingredients mix to produce product."),
            act("focus on product"),
        ]}
        self.assertTrue(chemistry_process(record)["read_mix_focus_order"])
        record["trace"][1], record["trace"][3] = record["trace"][3], record["trace"][1]
        self.assertFalse(chemistry_process(record)["read_mix_focus_order"])

    def test_incline_handles_block_names_and_goal_direction(self):
        for object_name in ("wood block", "steel block", "brick"):
            trace = trial(object_name, "C", 10) + trial(object_name, "H", 20)
            for goal, chosen in (("steepest", "C"), ("shallowest", "H")):
                record = {
                    "retrieval_query": f"Find the {goal} angle.",
                    "trace": trace + [act(f"focus on inclined plane {chosen}")],
                }
                audit = incline_process(record)
                self.assertTrue(audit["two_complete_trials"])
                self.assertTrue(audit["choice_supported_by_times"])
                self.assertEqual({item["object"] for item in audit["complete_trials"]}, {object_name})

    def test_incline_rejects_partial_or_different_object_trials(self):
        partial = trial("brick", "C", 10) + [
            act("move brick to inclined plane H"), act("activate stopwatch"),
            act("examine stopwatch", "The time reads 4 ticks."),
            act("deactivate stopwatch"), act("focus on inclined plane H"),
        ]
        self.assertFalse(incline_process({"retrieval_query": "Find the steepest angle.", "trace": partial})["two_complete_trials"])
        changed_object = trial("brick", "C", 10) + trial("steel block", "H", 20) + [act("focus on inclined plane H")]
        self.assertFalse(incline_process({"retrieval_query": "Find the shallowest angle.", "trace": changed_object})["two_complete_trials"])


if __name__ == "__main__":
    unittest.main()
