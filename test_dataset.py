"""Offline release checks; no environment imports or paid calls."""

import copy
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

import build_dataset as builder
from datasets.v1 import use_dataset as release


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = builder.build()
        cls.rows = [json.loads(line) for line in cls.files["episodes.jsonl"].splitlines()]

    def test_full_source_rebuild_matches_release(self):
        for name, data in self.files.items():
            self.assertEqual(data, (builder.RELEASE / name).read_bytes(), name)

    def test_coverage_and_failures(self):
        result = release.check()
        self.assertEqual(result["episodes"], 984)
        self.assertEqual(result["failures"], 77)
        self.assertEqual(result["batches"], 7)
        self.assertEqual(len(release.summaries(self.rows)), 24)

    def test_null_timing_not_imputed(self):
        self.assertEqual(sum(r["end_to_end_ms"] is None for r in self.rows), 846)
        for r in self.rows:
            self.assertEqual(r["end_to_end_ms"], r["runner_ms"])
        old = next(r for r in release.summaries(self.rows) if r["batch_id"] == "alfworld_v5")
        self.assertIsNone(old["average_end_to_end_ms"])

    def test_sensitive_text_excluded_even_if_source_gains_fields(self):
        r = dict(self.rows[0], latency_ms=1, trace=[])
        r.update(api_key="DO-NOT-EXPORT", initial_observation="PRIVATE", final_text="PRIVATE", game_file="PRIVATE")
        projected = builder.normalize(r, "a", "results/a.jsonl", 1, "a", "b")
        self.assertNotIn("PRIVATE", json.dumps(projected))
        self.assertNotIn("DO-NOT-EXPORT", json.dumps(projected))
        self.assertEqual(set(projected), set(builder.FIELDS))

    def test_duplicate_and_bad_metrics_rejected(self):
        with self.assertRaises(ValueError):
            release.validate_rows([self.rows[0], self.rows[0]], builder.schema())
        for field, value in [("total_tokens", -1), ("input_tokens", float("nan")), ("success", 1), ("end_to_end_ms", 123)]:
            r = dict(self.rows[0], **{field: value})
            with self.assertRaises(ValueError, msg=field):
                release.validate_rows([r], builder.schema())

    def test_pairing_and_unknown_prompts(self):
        pairs = release.paired(self.rows, "semantic_top3", "semantic_flat_retrieval", "semantic_body_retrieval")
        self.assertEqual(len(pairs), 18)
        self.assertEqual(sum(p["same_skill_prompt"] is True for p in pairs), 12)
        self.assertEqual(sum(p["right_minus_left_total_tokens"] for p in pairs), -269283)
        old = release.paired(self.rows, "alfworld_v5", "no_skill", "all_skills")
        self.assertTrue(all(p["same_skill_prompt"] is None for p in old))
        with self.assertRaises(ValueError):
            release.paired(self.rows[1:], "alfworld_v5", "no_skill", "all_skills")
        with self.assertRaises(ValueError):
            release.paired(self.rows, "unknown", "no_skill", "all_skills")

    def test_failure_cost_included_zero_success_undefined(self):
        rows = copy.deepcopy(self.rows[:2])
        for r in rows:
            r.update(batch_id="example", condition="same", cost_usd=2)
        rows[0]["success"], rows[1]["success"] = True, False
        self.assertEqual(release.summaries(rows)[0]["cost_per_successful_task_usd"], 4)
        rows[0]["success"] = False
        self.assertIsNone(release.summaries(rows)[0]["cost_per_successful_task_usd"])
        rows[0]["success"], rows[1]["cost_usd"] = True, None
        self.assertIsNone(release.summaries(rows)[0]["cost_per_successful_task_usd"])

    def test_csv_equivalence(self):
        csv_rows = list(csv.DictReader(io.StringIO(self.files["episodes.csv"].decode())))
        for a, b in zip(csv_rows, self.rows):
            for field, value in b.items():
                expected = "" if value is None else json.dumps(value, ensure_ascii=False) if isinstance(value, (list, bool)) else str(value)
                self.assertEqual(a[field], expected)
        self.assertEqual(len(csv_rows), len(self.rows))

    def test_standalone_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, data in self.files.items():
                (Path(folder) / name).write_bytes(data)
            self.assertEqual(release.check(folder)["episodes"], 984)
            (Path(folder) / "episodes.jsonl").write_bytes(b"{}\n")
            with self.assertRaises(ValueError):
                release.check(folder)


if __name__ == "__main__":
    unittest.main()
