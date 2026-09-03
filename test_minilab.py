import io
import http.client
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from agent import Agent, DeepSeekChatClient, ReferenceReplayClient, TOOL_SCHEMAS, initial_messages
from experiment import CONDITIONS, append_jsonl, run_episode, select_skills
from failure_matrix import failure_rows, main as failure_matrix_main
from failure_summary import summarize_failures
from minilab import MiniLab, ToolError, self_check, skill_check
from result_utils import deduplicate_records
from skills import SKILLS, render
from summarize_results import summarize_by_repeat
from plot_alfworld_results import failure_matrix, plot_rows
from tasks import V4_TASK_IDS


class MiniLabTest(unittest.TestCase):
    def test_all_reference_runs_pass(self):
        self.assertEqual(self_check(), {"success": True, "tasks": 58, "failures": []})

    def test_v4_suite_is_a_frozen_thirty_task_set(self):
        self.assertEqual(len(V4_TASK_IDS), 30)
        self.assertEqual(V4_TASK_IDS[:2], ("mix-01", "mix-02"))
        self.assertEqual(V4_TASK_IDS[-1], "hard-18")

    def test_path_cannot_escape_workspace(self):
        with MiniLab() as lab:
            lab.reset("text-01")
            with self.assertRaises(ToolError):
                lab.call_tool("read_file", path="../outside.txt")

    def test_calculator_rejects_code(self):
        with MiniLab() as lab:
            lab.reset("calc-01")
            with self.assertRaises(ToolError):
                lab.call_tool("calculate", expression="__import__('os').getcwd()")

    def test_grader_checks_state_instead_of_tool_claims(self):
        with MiniLab() as lab:
            lab.reset("text-02")
            self.assertFalse(lab.grade()["success"])
            lab.call_tool("write_file", path="output/greeting.txt", content="wrong\n")
            self.assertFalse(lab.grade()["success"])
            lab.call_tool("write_file", path="output/greeting.txt", content="hello mini lab\n")
            self.assertTrue(lab.grade()["success"])

    def test_fixed_skill_library_has_thirty_complete_entries(self):
        self.assertEqual(skill_check(), {"success": True, "skills": 30, "failures": []})
        rendered = render(SKILLS["csv-analysis"])
        for heading in ("Name", "Description", "Activation Condition", "Procedure", "Termination Condition"):
            self.assertIn(heading, rendered)
        self.assertIn("1.", rendered)

    def test_agent_loop_runs_without_access_to_the_grader(self):
        episode = Agent(ReferenceReplayClient("calc-01")).run("calc-01")
        self.assertTrue(episode.success)
        self.assertEqual([item["tool"] for item in episode.trace], ["calculate", "submit"])
        task = MiniLab()
        try:
            spec = task.reset("calc-01")
            prompt = initial_messages(spec)[1]["content"]
            self.assertNotIn("success_condition", prompt)
            self.assertNotIn(spec["success_condition"], prompt)
        finally:
            task.close()

    def test_agent_accepts_a_model_calling_a_real_tool_name(self):
        class DirectToolClient:
            calls = 0

            def respond(self, _messages):
                self.calls += 1
                if self.calls == 1:
                    return {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "direct-sort",
                            "type": "function",
                            "function": {
                                "name": "sort_data",
                                "arguments": '{"source":"data/scores.csv","destination":"output/scores.csv","column":"score","numeric":true}',
                            },
                        }],
                    }
                return {"role": "assistant", "content": "done"}

        episode = Agent(DirectToolClient()).run("csv-02")
        self.assertTrue(episode.success)
        self.assertEqual(episode.trace[0]["tool"], "sort_data")

    def test_experiment_conditions_and_jsonl_record(self):
        self.assertEqual(set(CONDITIONS), {"no_skill", "all_skills", "flat_retrieval", "body_aware_retrieval", "oracle_skill"})
        self.assertEqual(select_skills("csv-02", "no_skill").names, [])
        self.assertEqual(len(select_skills("csv-02", "all_skills").names), 30)
        self.assertEqual(select_skills("csv-02", "oracle_skill").names, ["csv-sorting"])
        for condition in CONDITIONS:
            record = run_episode(
                "csv-02", condition, "deepseek-v4-flash", 0, 0, "test-run",
                lambda: ReferenceReplayClient("csv-02"),
            )
            self.assertTrue(record["success"])
            self.assertEqual(record["skills_loaded"], select_skills("csv-02", condition).names)
            self.assertIn("total_tokens", record)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            append_jsonl(path, record)
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 1)

    def test_failure_matrix_only_shows_failed_task_conditions(self):
        base = {
            "run_id": "run-1", "task_id": "csv-02", "skills_loaded": ["csv-sorting"],
            "gold_skills": ["csv-sorting"], "retrieval_rank": 1, "gold_skill_ranks": [1],
            "final_text": "", "trace": [],
        }
        rows = failure_rows([
            {**base, "condition": "flat_retrieval", "repeat": 0, "success": True},
            {**base, "condition": "flat_retrieval", "repeat": 1, "success": False},
            {**base, "condition": "oracle_skill", "repeat": 0, "success": True},
        ], ["flat_retrieval", "oracle_skill"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["condition"], "flat_retrieval")
        self.assertEqual(rows[0]["failures"], 1)

    def test_failure_matrix_reports_unknown_run_id(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            path.write_text('{"run_id":"other","condition":"flat_retrieval"}\n', encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["failure_matrix.py", str(path), "--run-id", "missing"]), redirect_stdout(output):
                self.assertEqual(failure_matrix_main(), 2)
            self.assertIn("run_id_not_found", output.getvalue())

    def test_deduplicate_keeps_the_first_saved_episode(self):
        records, removed = deduplicate_records([
            {"run_id": "v2", "task_index": 0, "condition": "no_skill", "repeat": 0, "success": False},
            {"run_id": "v2", "task_index": 0, "condition": "no_skill", "repeat": 0, "success": True},
        ])
        self.assertEqual(removed, 1)
        self.assertFalse(records[0]["success"])

    def test_repeat_stats_average_runs_before_calculating_standard_deviation(self):
        records = [
            {"condition": "no_skill", "repeat": 0, "success": True, "input_tokens": 100, "output_tokens": 0, "total_tokens": 100, "latency_ms": 10, "cost_usd": 1, "tool_calls": 1},
            {"condition": "no_skill", "repeat": 0, "success": False, "input_tokens": 200, "output_tokens": 0, "total_tokens": 200, "latency_ms": 20, "cost_usd": 1, "tool_calls": 2},
            {"condition": "no_skill", "repeat": 1, "success": True, "input_tokens": 300, "output_tokens": 0, "total_tokens": 300, "latency_ms": 30, "cost_usd": 1, "tool_calls": 3},
            {"condition": "no_skill", "repeat": 1, "success": True, "input_tokens": 400, "output_tokens": 0, "total_tokens": 400, "latency_ms": 40, "cost_usd": 1, "tool_calls": 4},
        ]
        summary = summarize_by_repeat(records)[0]
        self.assertEqual(summary["episodes_per_repeat"], [2, 2])
        self.assertAlmostEqual(summary["task_success_rate"]["mean"], 0.75)
        self.assertAlmostEqual(summary["task_success_rate"]["std"], 0.3535533905932738)
        self.assertAlmostEqual(summary["average_total_tokens"]["mean"], 250)

    def test_failure_summary_keeps_trajectories_out_of_the_output(self):
        records = [
            {"condition": "no_skill", "task_id": "valid_unseen:001", "success": False, "tool_calls": 50, "task_family": "heat", "trace": [{"result": {"ok": False}}]},
            {"condition": "no_skill", "task_id": "valid_unseen:001", "success": True, "tool_calls": 4, "task_family": "heat", "trace": []},
        ]
        conditions, tasks = summarize_failures(records)
        self.assertEqual(conditions[0]["failures"], 1)
        self.assertEqual(conditions[0]["episodes_at_50_tool_calls"], 1)
        self.assertEqual(conditions[0]["failed_episodes_with_rejected_actions"], 1)
        self.assertEqual(tasks, [{"task_id": "valid_unseen:001", "failures_by_condition": {"no_skill": 1}}])

    def test_plot_rows_use_repeat_level_statistics(self):
        records = [
            {"condition": "no_skill", "repeat": 0, "success": True, "input_tokens": 10, "output_tokens": 2, "total_tokens": 12, "latency_ms": 4, "cost_usd": 1, "tool_calls": 1},
            {"condition": "no_skill", "repeat": 1, "success": False, "input_tokens": 20, "output_tokens": 4, "total_tokens": 24, "latency_ms": 8, "cost_usd": 1, "tool_calls": 2},
        ]
        rows = plot_rows(records)
        self.assertEqual(rows[0]["label"], "No Skill")
        self.assertEqual(rows[0]["average_total_tokens"]["mean"], 18)

    def test_failure_matrix_counts_failures_by_task_and_condition(self):
        records = [
            {"task_id": "valid_unseen:001", "condition": "no_skill", "success": False},
            {"task_id": "valid_unseen:001", "condition": "no_skill", "success": True},
        ]
        task_ids, matrix = failure_matrix(records)
        self.assertEqual(task_ids, ["valid_unseen:001"])
        self.assertEqual(matrix[0][0], 1)

    def test_retrieval_metrics_use_all_gold_skills(self):
        from retrieval_benchmark import rank_metrics

        metrics = rank_metrics(["noise", "gold-a", "gold-b", "gold-c"], ["gold-a", "gold-b", "gold-c"])
        self.assertEqual(metrics["gold_ranks"], [2, 3, 4])
        self.assertEqual(metrics["recall_at_3"], 2 / 3)
        self.assertEqual(metrics["hit_at_3"], 1.0)
        self.assertEqual(metrics["all_gold_at_3"], 0.0)
        self.assertEqual(metrics["mrr"], 0.5)
        self.assertEqual(metrics["primary_gold"], "gold-b")
        self.assertEqual(metrics["primary_rank"], 3)
        self.assertEqual(metrics["primary_hit_at_3"], 1.0)

    def test_primary_gold_rank_does_not_use_a_support_skill(self):
        from analyze_alfworld_formal import primary_gold_rank

        self.assertEqual(primary_gold_rank({"gold_skill_ranks": [1, 3, 2]}), 3)
        self.assertIsNone(primary_gold_rank({"gold_skill_ranks": [1, None, 2]}))

    def test_simple_pick_place_uses_task_language(self):
        from alfworld_skills import SKILLS as ALFWORLD_SKILLS, render as render_alfworld_skill

        text = render_alfworld_skill(ALFWORLD_SKILLS["simple-pick-place"])
        self.assertIn("put some object in or on", text)

    def test_heldout_selection_is_balanced_and_disjoint(self):
        from freeze_heldout_suite import FAMILIES, select_heldout

        games = [f"/data/{prefix}-task-{number}/trial/game.tw-pddl" for prefix in FAMILIES for number in range(6)]
        selected = select_heldout(games, {0, 6, 12, 18, 24, 30})
        self.assertEqual(len(selected), 30)
        self.assertFalse(set(selected) & {0, 6, 12, 18, 24, 30})

        from alfworld_suites import ALFWORLD_V2_30, ALFWORLD_V3_HELDOUT_30, validate_suites
        self.assertFalse(set(ALFWORLD_V2_30) & set(ALFWORLD_V3_HELDOUT_30))
        self.assertEqual(validate_suites(), [])

    def test_semantic_ranker_orders_cosine_scores(self):
        import numpy as np
        from retrieval_benchmark import semantic_ranker

        class FakeModel:
            def encode(self, text, **_kwargs):
                if isinstance(text, list):
                    return np.array([[1.0, 0.0]] + [[0.0, 1.0]] * (len(text) - 1))
                return np.array([1.0, 0.0])

        documents = [str(index) for index in range(30)]
        self.assertEqual(semantic_ranker(FakeModel(), documents)("query")[0], "task-goal-parse")

    def test_retrieval_error_categories_are_paired_by_task(self):
        from retrieval_error_analysis import compare

        base = {"task_id": "valid_unseen:001", "task_family": "heat", "query": "heat apple", "primary_gold": "execute-heat-place", "top_3": "[]"}
        rows = [
            {**base, "method": "bm25_body", "primary_hit_at_3": "1.0", "primary_rank": "1"},
            {**base, "method": "semantic_body", "primary_hit_at_3": "0.0", "primary_rank": "4"},
        ]
        result = compare(rows)[0]
        self.assertEqual(result["category"], "bm25_only")
        self.assertEqual(result["diagnosis"], "semantic_ranking_error")
        self.assertEqual(result["semantic_minus_bm25_rank"], 3)

    def test_deepseek_client_retries_an_incomplete_response(self):
        payload = io.BytesIO(b'{"usage":{"prompt_tokens":1,"completion_tokens":1},"choices":[{"message":{"role":"assistant","content":"ok"}}]}')
        client = DeepSeekChatClient("deepseek-v4-flash", api_key="test-key")
        with patch("agent.urllib.request.urlopen", side_effect=[http.client.IncompleteRead(b""), payload]) as request, patch("agent.time.sleep"):
            self.assertEqual(client.respond([{"role": "user", "content": "test"}])["content"], "ok")
        self.assertEqual(request.call_count, 2)

    def test_submit_type_is_exposed_without_exposing_the_answer(self):
        with MiniLab() as lab:
            code_task = lab.reset("text-01")
            amount_task = lab.reset("csv-08")
        self.assertEqual(code_task["answer_json_type"], "string")
        self.assertEqual(amount_task["answer_json_type"], "number")
        prompt = initial_messages(code_task)[1]["content"]
        self.assertIn("Answer JSON type for submit: string", prompt)
        self.assertNotIn(code_task["success_condition"], prompt)
        submit_schema = next(item for item in TOOL_SCHEMAS if item["function"]["name"] == "submit")
        self.assertIn("oneOf", submit_schema["function"]["parameters"]["properties"]["value"])


if __name__ == "__main__":
    unittest.main()
