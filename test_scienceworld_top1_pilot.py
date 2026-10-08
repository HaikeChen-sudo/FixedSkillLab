import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scienceworld_agent as agent
import scienceworld_top1_pilot as pilot
from scienceworld_skills import loaded_skill_text


class FakeClient:
    messages = None

    def __init__(self, *_args, **_kwargs):
        pass

    def respond(self, messages):
        FakeClient.messages = copy.deepcopy(messages)
        return {"role": "assistant", "content": "stop"}

    def metrics(self):
        return dict(input_tokens=100, output_tokens=10, prompt_cache_hit_tokens=0, prompt_cache_miss_tokens=100)


class FakeEnv:
    def __init__(self, query):
        self.query = query

    def load(self, *_args, **_kwargs):
        pass

    def reset(self):
        return "room", dict(taskDesc=self.query, score=0, moves=0)

    def close(self):
        pass


class Top1PilotTests(unittest.TestCase):
    def setUp(self):
        self.manifest = pilot.current_manifest()

    def result(self, case, mode):
        return dict(hits=case["ranking"][mode][:3], metadata=dict(
            retriever="scienceworld-minilm-l6-v2-v1", top_k=3, index_mode=mode,
            query_sha256=case["query_sha256"], truncated=False))

    def record(self, expected):
        case = self.manifest["cases"][f"{expected['task_name']}:v{expected['variation']:03d}"]
        mode = "flat" if expected["condition"] == "semantic_flat_top1" else "body"
        with patch.object(agent, "make_env", return_value=FakeEnv(case["query"])), \
                patch.object(agent, "DeepSeekChatClient", FakeClient), \
                patch.object(agent, "strong_retrieve", return_value=self.result(case, mode)):
            row = agent.run_episode(pilot.MODEL, 0.0, expected["task_name"], expected["variation"],
                                    "easy", pilot.LIMIT, expected["condition"])
        row.update(expected, run_id=pilot.RUN_ID, thinking="disabled", variation_split="dev",
                   top1_manifest_sha256="test-manifest", runner_ms=row["latency_ms"])
        return row

    def test_plan_has_36_distinct_balanced_episodes(self):
        plan = pilot.plan()
        self.assertEqual(len(plan), 36)
        self.assertEqual(len({(r["task_name"], r["variation"], r["condition"], r["repeat"]) for r in plan}), 36)
        for task, variation in pilot.CASES:
            for condition in pilot.CONDITIONS:
                rows = [r for r in plan if (r["task_name"], r["variation"], r["condition"]) == (task, variation, condition)]
                self.assertEqual(sorted(r["order_position"] for r in rows), [0, 1, 2])

    def test_top1_slices_without_changing_router_or_injecting_gold(self):
        case = self.manifest["cases"]["find-non-living-thing:v150"]
        for condition, mode in (("semantic_flat_top1", "flat"), ("semantic_body_top1", "body")):
            original = self.result(case, mode)
            with patch.object(agent, "strong_retrieve", return_value=original) as router:
                selection = agent.skill_selection(condition, case["task_name"], case["query"])
            router.assert_called_once_with(case["query"], mode == "body", "v3", "minilm")
            self.assertEqual(selection.names, [case["top1"][mode]])
            self.assertEqual(selection.gold_skill_ranks, [None if mode == "flat" else 1])
            self.assertEqual(selection.retrieval_metadata["top_k"], 1)
            self.assertEqual(len(original["hits"]), 3)
            self.assertEqual(original["metadata"]["top_k"], 3)
        self.assertEqual(agent.DEFAULT_CONDITIONS, ("no_skill", "oracle_v2"))

    def test_agent_loads_one_full_skill_and_no_skill_stays_empty(self):
        for condition in pilot.CONDITIONS:
            expected = next(r for r in pilot.plan() if r["condition"] == condition)
            row = self.record(expected)
            pilot.validate_record(row, expected, self.manifest, "test-manifest")
            guidance = [m["content"] for m in FakeClient.messages if m["content"].startswith("Fixed Skill guidance:")]
            if condition == "no_skill":
                self.assertEqual(guidance, [])
            else:
                self.assertEqual(len(row["skills_loaded"]), 1)
                self.assertEqual(guidance, ["Fixed Skill guidance:\n" + loaded_skill_text(row["skills_loaded"], "v3")])

    def test_resume_rejects_duplicates_budget_and_prompt_changes(self):
        expected = next(r for r in pilot.plan() if r["condition"] == "semantic_flat_top1")
        row = self.record(expected)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "results.jsonl"
            path.write_text(json.dumps(row) + "\n")
            self.assertEqual(len(pilot.saved_records(path, self.manifest, "test-manifest")), 1)
            path.write_text((json.dumps(row) + "\n") * 2)
            with self.assertRaises(ValueError):
                pilot.saved_records(path, self.manifest, "test-manifest")
        for field, changed in (("environment_max_steps", 200), ("skill_prompt_sha256", "changed"),
                               ("run_id", "old"), ("total_tokens", 0)):
            altered = dict(row, **{field: changed})
            with self.assertRaises(ValueError):
                pilot.validate_record(altered, expected, self.manifest, "test-manifest")

    def test_default_preview_never_calls_api_or_environment(self):
        with patch.object(pilot, "run_episode", side_effect=AssertionError("paid call")), \
                patch.object(pilot, "preflight", side_effect=AssertionError("environment call")):
            self.assertEqual(pilot.main([]), 0)


if __name__ == "__main__":
    unittest.main()
