import math
import unittest

from scienceworld_retrieval_baselines import bm25_scores, ranked, summarize


class RetrievalBaselinesTests(unittest.TestCase):
    def test_bm25_hand_calculation_and_empty_documents(self):
        scores = bm25_scores("water water", ["water water", "fire"])
        idf = math.log(2)
        expected = 2 * idf * 2 * 2.5 / (2 + 1.5 * (0.25 + 0.75 * 2 / 1.5))
        self.assertAlmostEqual(scores[0], expected)
        self.assertEqual(scores[1], 0)
        self.assertEqual(bm25_scores("water", ["", ""]), [0, 0])
        with self.assertRaises(ValueError):
            bm25_scores("water", [])

    def test_bm25_matches_existing_alfworld_convention(self):
        from alfworld_retrieval import SKILL_LIST, retrieve_bm25, skill_text
        for body in (False, True):
            names = [skill.name for skill in SKILL_LIST]
            documents = [skill_text(skill, body) for skill in SKILL_LIST]
            query = "clean a plate plate then put it on the table"
            result = ranked(names, bm25_scores(query, documents))[:3]
            expected = [vars(row) for row in retrieve_bm25(query, body)]
            self.assertEqual(result, expected)

    def test_ranking_uses_unrounded_scores_then_names(self):
        result = ranked(["a", "b", "c"], [0.3, 0.30000001, 0.3])
        self.assertEqual([row["name"] for row in result], ["b", "a", "c"])
        for names, scores in ((["a"], []), (["a", "a"], [0, 1]), (["a"], [math.nan])):
            with self.assertRaises(ValueError):
                ranked(names, scores)

    def test_run_membership_and_repeated_query_denominators(self):
        from scienceworld_retrieval_baselines import METHODS
        cases = [dict(library_version="v3", query_sha256="same", gold_skill="gold",
                      source_records=[{"run_id": "run"}, {"run_id": "run"}],
                      comparisons={mode: {method: {"gold_rank": 2} for method in METHODS}
                                   for mode in ("flat", "body")}) for _ in range(2)]
        result = summarize(cases)
        self.assertEqual(result["by_library"][0]["cases"], 2)
        self.assertEqual(result["by_run"][0]["cases"], 2)
        self.assertEqual(result["by_library_unique_query_gold"][0]["cases"], 1)
        self.assertEqual(result["by_library"][0]["mrr"], 0.5)


if __name__ == "__main__":
    unittest.main()
