import unittest

from scienceworld_budget_audit import breakdown, gold_process, replay, same_prefix


class FakeEnv:
    def reset(self):
        self.moves = 0
        return "initial", {"moves": 0, "score": 0}

    def step(self, command):
        self.moves += 2 if command == "wait1" else 1
        return command, 0, self.moves > self.envStepLimit, {"moves": self.moves, "score": 0}


class BudgetAuditTests(unittest.TestCase):
    def test_budget_boundary_and_same_path(self):
        commands = ["wait1"] * 4
        short = replay(FakeEnv(), commands, 3)
        long = replay(FakeEnv(), commands, 20)
        self.assertEqual(short["environment_moves"], 4)
        self.assertEqual(short["termination_reason"], "environment_budget")
        self.assertTrue(same_prefix(short, long))
        long["trace"][0]["result"]["observation"] = "different state"
        self.assertFalse(same_prefix(short, long))

    def test_official_command_aliases(self):
        from test_scienceworld_procedure_audit_v2 import act, trial

        trace = trial("brick", "B", 22) + trial("brick", "F", 24)
        trace += [act("focus on inclined plane F")]
        for action in trace:
            action["command"] = action["command"].replace("stopwatch", "stopwatch in inventory")
            action["command"] = action["command"].replace("examine inclined plane", "look at inclined plane")
        result = gold_process({"trace": trace, "task_description": "Find the shallowest angle."})
        self.assertTrue(result["two_complete_trials"])
        self.assertTrue(result["choice_supported_by_times"])
        self.assertIn("in inventory", trace[1]["command"])

    def test_moves_are_not_action_counts(self):
        record = replay(FakeEnv(), ["wait1", "examine plane", "pick up block"], 20)
        record.update(task_id="test", condition="gold")
        result = breakdown(record)
        self.assertEqual(result["buckets"]["waiting"], {"actions": 1, "moves": 2})
        self.assertEqual(sum(b["moves"] for b in result["buckets"].values()), 4)
        record["environment_moves"] = 5
        with self.assertRaises(ValueError):
            breakdown(record)


if __name__ == "__main__":
    unittest.main()
