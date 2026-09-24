import copy
import hashlib
import unittest

from scienceworld_skills import library_hash, versioned_skills
from scienceworld_top1_audit import counts, select_cases, summarize


class Top1AuditTests(unittest.TestCase):
    def fixture(self):
        names = [skill.name for skill in versioned_skills("v4d")]
        ranking = [dict(name=name, rank=i) for i, name in enumerate(names, 1)]
        return dict(task_id="power-component:v010", library_version="v4d",
                    library_sha256=library_hash("v4d"), query="seen task",
                    query_sha256=hashlib.sha256(b"seen task").hexdigest(), gold_skill=names[0],
                    source_records=[dict(variation_split="dev")],
                    comparisons={mode: dict(minilm=dict(ranking=ranking, gold_rank=1))
                                 for mode in ("flat", "body")})

    def test_official_test_excluded_even_when_source_claims_dev(self):
        selected, excluded = select_cases([self.fixture()],
                                          {"power-component": dict(train=[], dev=[], test=[10])})
        self.assertEqual(selected, [])
        self.assertEqual(excluded, {"test": 1})

    def test_duplicate_cases_and_identical_queries_do_not_inflate(self):
        row = self.fixture()
        other = copy.deepcopy(row)
        other["task_id"] = "power-component:v011"
        selected, _ = select_cases([row, copy.deepcopy(row), other],
                                   {"power-component": dict(train=[], dev=[10, 11], test=[])})
        summary = summarize(selected)[0]
        self.assertEqual(summary["task_query_units"]["cases"], 2)
        self.assertEqual(summary["unique_query_gold"]["cases"], 1)

    def test_four_outcomes_and_both_wrong_disagreement(self):
        rows = [dict(gold_skill="gold", top1=dict(flat=f, body=b)) for f, b in
                [("gold", "gold"), ("gold", "wrong"), ("wrong", "gold"), ("wrong", "other")]]
        result = counts(rows)
        self.assertEqual([result[k] for k in ("both_hit", "flat_only", "body_only", "both_miss")], [1]*4)
        self.assertEqual(result["different_top1"], 3)

    def test_invalid_hash_and_overlap_are_rejected(self):
        row = self.fixture()
        with self.assertRaises(ValueError):
            select_cases([row], {"power-component": dict(train=[10], dev=[10], test=[])})
        row["query"] = "changed"
        with self.assertRaises(ValueError):
            select_cases([row], {"power-component": dict(train=[], dev=[10], test=[])})

    def test_cached_gold_rank_must_match_full_ranking(self):
        row = self.fixture()
        row["comparisons"]["flat"]["minilm"]["gold_rank"] = 2
        with self.assertRaises(ValueError):
            select_cases([row], {"power-component": dict(train=[], dev=[10], test=[])})


if __name__ == "__main__":
    unittest.main()
