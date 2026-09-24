"""Interface checks use saved queries and test doubles, never a live Agent API."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import scienceworld_agent as agent
import scienceworld_strong_retrieval as router
from scienceworld_experiment import condition_list
from scienceworld_skills import loaded_skill_text


ROOT = Path(__file__).resolve().parent
SAVED_RANKINGS = ROOT / "results/scienceworld_retrieval_baselines_2026-09-24/rankings.jsonl"


def saved_cases():
    return [json.loads(line) for line in SAVED_RANKINGS.read_text(encoding="utf-8").splitlines()]


class FakeEnv:
    closed = False

    def load(self, *_args, **_kwargs):
        pass

    def reset(self):
        return "test room", {"taskDesc": "Your task is to boil tin.", "score": 0, "moves": 0}

    def close(self):
        self.closed = True


class RecordingClient:
    messages = None

    def __init__(self, *_args, **_kwargs):
        pass

    def respond(self, messages):
        RecordingClient.messages = messages[:]
        return {"role": "assistant", "content": "test stop"}

    def metrics(self):
        return {"input_tokens": 100, "output_tokens": 12,
                "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 100}


class StrongRetrievalTests(unittest.TestCase):
    def test_new_conditions_keep_old_defaults_and_library_choices(self):
        self.assertEqual(condition_list(",".join(router.STRONG_CONDITIONS)), list(router.STRONG_CONDITIONS))
        self.assertEqual(agent.DEFAULT_CONDITIONS, ("no_skill", "oracle_v2"))
        self.assertEqual(agent.skill_selection("oracle_v4", "power-component").library_version, "v4b")
        self.assertEqual(agent.skill_selection("oracle_v4c", "power-component").library_version, "v4c")
        query = "Compare inclined plane B and inclined plane F."
        self.assertEqual(agent.skill_selection("bm25_flat_retrieval", "inclined-plane-determine-angle", query).library_version, "v4d")
        self.assertEqual(agent.skill_selection("bm25_body_retrieval", "boil", query).library_version, "v3")
        for condition in router.STRONG_CONDITIONS:
            with self.assertRaises(ValueError):
                agent.skill_selection(condition, "boil", "")

    def test_bm25_replays_all_saved_top_three(self):
        for case in saved_cases():
            for mode in ("flat", "body"):
                with self.subTest(task=case["task_id"], version=case["library_version"], mode=mode):
                    result = router.strong_retrieve(case["query"], mode == "body", case["library_version"], "bm25")
                    self.assertEqual(result["hits"], case["comparisons"][mode]["bm25"]["ranking"][:3])
                    self.assertEqual(result["metadata"]["library_sha256"], case["library_sha256"])

    def test_gold_label_is_not_sent_to_the_router(self):
        result = router.local_result("Your task is to boil tin.", False, "v3", "bm25")
        with patch.object(agent, "strong_retrieve", return_value=result) as retrieve:
            selected = agent.skill_selection("semantic_flat_retrieval", "boil", "same query")
        retrieve.assert_called_once_with("same query", False, "v3", "minilm")
        self.assertEqual(selected.names, [hit["name"] for hit in result["hits"]])

    def test_agent_loads_full_ranked_skills_and_records_cost_boundaries(self):
        def fake_router(query, body, version, method):
            result = router.local_result(query, body, version, "bm25")
            result["metadata"]["retriever"] = router.RETRIEVERS[method]
            return result

        for condition, (method, body) in router.STRONG_CONDITIONS.items():
            with self.subTest(condition=condition):
                env = FakeEnv()
                with patch.object(agent, "make_env", return_value=env), \
                        patch.object(agent, "DeepSeekChatClient", RecordingClient), \
                        patch.object(agent, "strong_retrieve", side_effect=fake_router), \
                        patch.object(agent.time, "perf_counter", side_effect=[10, 11, 13, 18]):
                    record = agent.run_episode("test", 0, "boil", 0, "easy", 1, condition)
                expected = loaded_skill_text(record["skills_loaded"], "v3", "full")
                self.assertEqual(RecordingClient.messages[1]["content"], "Fixed Skill guidance:\n" + expected)
                self.assertIn("Procedure", expected)
                self.assertEqual(record["skill_render_mode"], "full")
                self.assertEqual(record["retriever"], router.RETRIEVERS[method])
                self.assertEqual(record["retrieval_metadata"]["index_mode"], "body" if body else "flat")
                self.assertEqual(record["routing_ms"], 2000)
                self.assertEqual(record["latency_ms"], 8000)
                self.assertEqual((record["input_tokens"], record["output_tokens"], record["total_tokens"]), (100, 12, 112))
                self.assertEqual(record["skills_loaded"], [hit["name"] for hit in record["retrieval"]])
                self.assertFalse(record["success"])
                self.assertTrue(env.closed)

    def test_retrieval_failure_stops_before_api_client(self):
        env = FakeEnv()
        with patch.object(agent, "make_env", return_value=env), \
                patch.object(agent, "strong_retrieve", side_effect=RuntimeError("local model missing")), \
                patch.object(agent, "DeepSeekChatClient") as client:
            with self.assertRaisesRegex(RuntimeError, "local model missing"):
                agent.run_episode("test", 0, "boil", 0, "easy", 1, "semantic_body_retrieval")
            client.assert_not_called()
        self.assertTrue(env.closed)

    def test_worker_failures_and_model_changes_do_not_fall_back(self):
        query = "Your task is to boil tin."
        with patch.object(router, "RETRIEVAL_PYTHON", ROOT / "missing-retrieval-runtime"):
            with self.assertRaisesRegex(ValueError, "missing"):
                router.strong_retrieve(query, False, "v3", "minilm")
        with patch.object(router, "RETRIEVAL_PYTHON", Path(sys.executable)):
            for result in (SimpleNamespace(returncode=1, stderr="test error", stdout=""),
                           SimpleNamespace(returncode=0, stderr="", stdout="{}")):
                with patch.object(router.subprocess, "run", return_value=result):
                    with self.assertRaises(RuntimeError):
                        router.strong_retrieve(query, False, "v3", "minilm")
            with patch.object(router.subprocess, "run", side_effect=subprocess.TimeoutExpired("worker", 120)):
                with self.assertRaisesRegex(RuntimeError, "timed out"):
                    router.strong_retrieve(query, False, "v3", "minilm")
        with patch.object(router, "local_encoder", return_value=(None, {"file_sha256": {}})):
            with self.assertRaisesRegex(ValueError, "frozen baseline"):
                router.local_result(query, False, "v3", "minilm")
        with patch.object(router, "library_hash", return_value="changed"):
            with self.assertRaisesRegex(ValueError, "frozen offline baseline"):
                router.strong_retrieve(query, False, "v3", "bm25")

    def test_oversized_encoder_input_fails_before_encoding(self):
        model = SimpleNamespace(max_seq_length=2, tokenizer=lambda *_args, **_kwargs: {"input_ids": [1, 2, 3]})
        with self.assertRaisesRegex(ValueError, "token limit"):
            router.minilm_scores("query", ["document"], model)


@unittest.skipUnless(os.environ.get("SCIENCEWORLD_LOCAL_RETRIEVAL_TESTS") == "1", "enable installed local-model checks explicitly")
class LocalMiniLMTests(unittest.TestCase):
    def test_actual_scienceworld_to_retrieval_environment_bridge(self):
        cases = saved_cases()
        selected = [next(row for row in cases if row["task_id"] == task and row["library_version"] == version)
                    for task, version in (("boil:v029", "v3"), ("inclined-plane-determine-angle:v086", "v4d"))]
        for case in selected:
            for mode in ("flat", "body"):
                with self.subTest(task=case["task_id"], mode=mode):
                    condition = "semantic_" + mode + "_retrieval"
                    result = agent.skill_selection(condition, case["task_name"], case["query"])
                    expected = case["comparisons"][mode]["minilm"]["ranking"][:3]
                    self.assertEqual(result.names, [hit["name"] for hit in expected])
                    for actual, previous in zip(result.retrieved, expected):
                        self.assertEqual(actual["rank"], previous["rank"])
                        self.assertLessEqual(abs(actual["score"] - previous["score"]), 0.000002)
                    self.assertEqual(result.retrieval_metadata["execution"], "cold_local_worker_per_request")
                    self.assertFalse(result.retrieval_metadata["truncated"])


if __name__ == "__main__":
    unittest.main()
