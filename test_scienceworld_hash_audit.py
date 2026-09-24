"""Regression and provenance checks for the saved-query collision audit."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scienceworld_hash_audit import compare_cases, load_cases, main, summarize


def incline_record():
    return {
        "run_id": "regression-1x1", "task_id": "inclined-plane-determine-angle:v086",
        "task_name": "inclined-plane-determine-angle", "condition": "flat_retrieval_v4d", "repeat": 0,
        "retriever": "hash-embedding-v1", "skill_library_version": "v4d",
        "skill_library_sha256": "5d16691dd48632b07fc2e176ec3daed70b7e089c59c28e7c434e4e06b3e04d0b",
        "retrieval_query": "Task Description:\nYour task is to determine which of the two inclined planes (B, F) has the shallowest angle. After completing your experiment, focus on the inclined plane with the shallowest angle.",
        "gold_skills": ["measure-inclined-plane-angle"], "gold_skill_ranks": [None],
        "skills_loaded": ["measure-and-classify-temperature", "freeze-substance", "chemistry-recipe-mix"],
        "retrieval": [
            {"name": "measure-and-classify-temperature", "score": 0.311811, "rank": 1},
            {"name": "freeze-substance", "score": 0.234206, "rank": 2},
            {"name": "chemistry-recipe-mix", "score": 0.223047, "rank": 3},
        ],
    }


class HashAuditTest(unittest.TestCase):
    def test_incline_recovery_and_repeat_deduplication(self):
        row = incline_record()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "episodes.jsonl"
            source.write_text(json.dumps(row) + "\n" + json.dumps(dict(row, repeat=1)) + "\n")
            cases, records, stats = load_cases(source)
        self.assertEqual((len(cases), len(records), stats["replayed_matching_records"]), (1, 2, 2))
        cases = compare_cases(cases)
        flat = cases[0]["comparisons"]["flat"]
        self.assertEqual(flat["hash_256"]["gold_rank"], 5)
        for method in ("hash_1024", "hash_4096", "hash_65536", "exact_counts"):
            self.assertEqual(flat[method]["gold_rank"], 1)
        summary = summarize(cases)
        self.assertTrue(all(row["cases"] == 1 for row in summary["by_library"]))
        self.assertEqual(summary["hash_256_to_exact"][0]["counts"], {"recovered_without_hashing": 1})

    def test_changed_library_or_saved_ranking_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "episodes.jsonl"
            for field, value in (("skill_library_sha256", "changed"), ("retrieval", []),
                                 ("gold_skill_ranks", [1]), ("retrieval_query", "")):
                with self.subTest(field=field):
                    row = incline_record()
                    row[field] = value
                    source.write_text(json.dumps(row) + "\n")
                    with self.assertRaises(ValueError):
                        load_cases(source)

    def test_exported_corpus_reproduces_rankings_without_raw_trajectories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "episodes.jsonl"
            source.write_text(json.dumps(incline_record()) + "\n")
            first, replay = root / "first", root / "replay"
            for input_file, output in ((source, first), (first / "source_records.jsonl", replay)):
                with patch("sys.argv", ["audit", str(input_file), "--output-dir", str(output)]):
                    with redirect_stdout(io.StringIO()):
                        self.assertEqual(main(), 0)
            self.assertEqual((first / "rankings.jsonl").read_bytes(), (replay / "rankings.jsonl").read_bytes())
            original = json.loads((first / "summary.json").read_text())
            rerun = json.loads((replay / "summary.json").read_text())
            self.assertEqual(original["by_library"], rerun["by_library"])
            with patch("sys.argv", ["audit", str(source), "--output-dir", str(first)]):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main()


if __name__ == "__main__":
    unittest.main()
