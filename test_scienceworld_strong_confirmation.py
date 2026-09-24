"""Confirmation accounting and resume checks use fake episodes, not DeepSeek."""

from collections import Counter, defaultdict
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import scienceworld_strong_confirmation as runner
from scienceworld_retrieval_baselines import digest
from scienceworld_skills import V4_GOLD_SKILLS, library_hash, loaded_skill_text, versioned_skills


def fake_episode(model, temperature, task, variation, simplification, steps, condition):
    version = "v4d" if task in V4_GOLD_SKILLS else "v3"
    names = [] if condition == "no_skill" else [skill.name for skill in versioned_skills(version)][:3]
    return dict(environment="scienceworld", task_id=f"{task}:v{variation:03d}", task_name=task,
                variation=variation, condition=condition, model=model, temperature=temperature,
                simplification=simplification, max_steps=steps, input_tokens=100, output_tokens=10,
                total_tokens=110, latency_ms=10, routing_ms=0, cost_usd=0.001, score=100, success=True,
                agent_protocol_version="scienceworld-v14b" if task in V4_GOLD_SKILLS else "scienceworld-v2",
                shared_controller_version="shared-state-checkpoint-v1" if task in V4_GOLD_SKILLS else None,
                skills_loaded=names, skill_library_version=version if names else None,
                skill_library_sha256=library_hash(version) if names else None,
                skill_prompt_sha256=digest(loaded_skill_text(names, version).encode()) if names else None,
                skill_render_mode="full" if names else None,
                retrieval=[dict(name=name) for name in names],
                retrieval_metadata=dict(method="minilm", truncated=False, library_sha256=library_hash(version),
                                        index_mode="flat" if condition == "semantic_flat_retrieval" else "body"))


class ConfirmationTests(unittest.TestCase):
    def test_frozen_cases_have_no_known_overlap_and_order_is_balanced(self):
        manifest, _ = runner.verify_manifest()
        selection = json.loads((runner.ROOT / "results/scienceworld_strong_confirmation_selection.json").read_text())
        eligible = [task for task, values in sorted(selection["official_test_variations"].items())
                    if set(values) - set(selection["excluded_variations"][task])]
        selected = [(task, min(set(selection["official_test_variations"][task]) -
                              set(selection["excluded_variations"][task]))) for task in eligible[:6]]
        self.assertEqual(selected, list(runner.CASES))
        self.assertEqual(manifest["settings"]["cases"], selection["cases"])
        plan = runner.episode_plan()
        self.assertEqual(len(plan), 54)
        self.assertEqual(len({runner.episode_key(row) for row in plan}), 54)
        counts = defaultdict(Counter)
        for row in plan:
            counts[row["task_name"], row["condition"]][row["order_position"]] += 1
        self.assertTrue(all(count == {0: 1, 1: 1, 2: 1} for count in counts.values()))

    def test_preview_cannot_start_environment_or_api(self):
        with patch.object(runner, "check_environment") as check, patch.object(runner, "run_episode") as run:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(runner.main([]), 0)
            self.assertEqual(json.loads(output.getvalue())["api_calls"], 0)
            check.assert_not_called()
            run.assert_not_called()

    def test_interrupted_run_resumes_only_missing_episodes(self):
        real_plan = runner.episode_plan()
        first = real_plan[:2]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "results.jsonl"
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-not-a-real-key"}), \
                    patch.object(runner, "check_environment"), \
                    patch.object(runner, "run_episode", side_effect=[fake_episode(
                        runner.MODEL, 0.0, row["task_name"], row["variation"], "easy", 100, row["condition"]
                    ) for row in first] + [RuntimeError("test connection interrupted")]):
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "interrupted"):
                    runner.main(["--execute", "--results", str(path)])
            self.assertEqual(len(path.read_text().splitlines()), 2)
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-not-a-real-key"}), \
                    patch.object(runner, "check_environment"), \
                    patch.object(runner, "run_episode", side_effect=fake_episode) as run:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(runner.main(["--execute", "--resume", "--results", str(path)]), 0)
                self.assertEqual(run.call_count, 52)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(runner.main(["--execute", "--resume", "--results", str(path)]), 0)
                self.assertEqual(run.call_count, 52)

    def test_duplicate_and_invalid_resume_records_fail(self):
        row = runner.episode_plan()[0]
        _, manifest_sha = runner.verify_manifest()
        record = fake_episode(runner.MODEL, 0.0, row["task_name"], row["variation"], "easy", 100, row["condition"])
        record.update(row, run_id=runner.RUN_ID, suite="scienceworld-strong-confirm-6", variation_split="test",
                      order_seed=runner.ORDER_SEED, thinking="disabled", runner_ms=12,
                      confirmation_manifest_sha256=manifest_sha)
        runner.validate_record(record, row, manifest_sha)
        for field, value in (("total_tokens", 9), ("cost_usd", None), ("cost_usd", float("nan")),
                             ("model", "different-model"), ("success", False),
                             ("confirmation_manifest_sha256", "changed")):
            changed = copy.deepcopy(record)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                runner.validate_record(changed, row, manifest_sha)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.jsonl"
            runner.append_jsonl(path, record)
            runner.append_jsonl(path, record)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                runner.completed_records(path, runner.episode_plan(), manifest_sha)

    def test_environment_failure_and_cost_stop_prevent_next_api_call(self):
        with tempfile.TemporaryDirectory() as folder:
            args = ["--execute", "--results", str(Path(folder) / "rows.jsonl")]
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-not-a-real-key"}), \
                    patch.object(runner, "check_environment", side_effect=ValueError("split mismatch")), \
                    patch.object(runner, "run_episode") as run:
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "split mismatch"):
                    runner.main(args)
                run.assert_not_called()
            def expensive_episode(*values):
                record = fake_episode(*values)
                record["cost_usd"] = 0.51
                return record
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-not-a-real-key"}), \
                    patch.object(runner, "check_environment"), \
                    patch.object(runner, "run_episode", side_effect=expensive_episode) as run:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(runner.main(args), 2)
                    self.assertEqual(runner.main(args + ["--resume"]), 2)
                self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
