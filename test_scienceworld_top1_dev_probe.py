import unittest

from scienceworld_skills import GOLD_SKILLS
from scienceworld_top1_dev_probe import choose_cases, seen_json, summary


class DevProbeTests(unittest.TestCase):
    def test_fixed_balanced_selection_ignores_input_order_and_seen_ids(self):
        splits = {task: dict(train=[0], dev=[4, 2, 3, 1], test=[5]) for task in GOLD_SKILLS}
        cases = choose_cases(splits, {(task, 1) for task in GOLD_SKILLS})
        self.assertEqual(len(cases), 12)
        for task in GOLD_SKILLS:
            self.assertEqual([r["variation"] for r in cases if r["task_name"] == task], [2, 3])

    def test_split_overlap_and_insufficient_dev_pool_fail(self):
        splits = {task: dict(train=[0], dev=[1, 2], test=[3]) for task in GOLD_SKILLS}
        task = next(iter(GOLD_SKILLS))
        with self.assertRaises(ValueError):
            choose_cases(splits, {(task, 1)})
        splits[task]["test"] = [2]
        with self.assertRaises(ValueError):
            choose_cases(splits, set())

    def test_history_recognizes_ids_rows_pairs_and_repeated_queries(self):
        seen, queries = set(), set()
        seen_json([{"task_id": "boil:v014", "query": "old"},
                   {"task_name": "freeze", "variation": 15, "retrieval_query": "old"},
                   ["melt", 16], "use-thermometer:v270"], seen, queries)
        self.assertEqual(seen, {("boil", 14), ("freeze", 15), ("melt", 16), ("use-thermometer", 270)})
        self.assertEqual(len(queries), 1)

    def test_order_difference_is_not_a_set_difference(self):
        row = dict(gold_skill="a", top1=dict(flat="a", body="b"),
                   top3=dict(flat=["a", "b", "c"], body=["b", "a", "c"]),
                   gold_rank=dict(flat=1, body=2),
                   prompt_sha256=dict(flat={"1": "a", "3": "abc"}, body={"1": "b", "3": "bac"}))
        result = summary([row])
        self.assertEqual(result["different_top1"], 1)
        self.assertEqual(result["flat_only"], 1)
        self.assertEqual(result["different_top3_set"], 0)
        self.assertEqual(result["different_top3_ordered"], 1)
        self.assertEqual(result["body_hit_at_3"], 1)
        self.assertEqual(result["same_top3_prompt"], 0)


if __name__ == "__main__":
    unittest.main()
