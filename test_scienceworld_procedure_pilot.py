"""No-network checks for the frozen Procedure pilot runner."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scienceworld_procedure_pilot import existing_records, plan, run_arm
from scienceworld_skills import library_hash


class FakeEnv:
    def load(self, *_args, **_kwargs):
        pass

    def reset(self):
        return "room", {"taskDesc": "Complete the task.", "score": 0, "moves": 0}

    def close(self):
        pass


class StopClient:
    prompts = []

    def __init__(self, *_args, **_kwargs):
        pass

    def respond(self, messages):
        self.prompts.append([message["content"] for message in messages if message["role"] == "system"])
        return {"role": "assistant", "content": "stop"}

    def metrics(self):
        return {"input_tokens": 0, "output_tokens": 0, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0}


class ProcedurePilotTests(unittest.TestCase):
    def test_four_arms_share_agent_protocol_and_restore_library(self):
        rows = plan()
        self.assertEqual(len(rows), 4)
        original_hash = library_hash("v4b")
        StopClient.prompts = []
        with patch("scienceworld_agent.make_env", return_value=FakeEnv()), patch("scienceworld_agent.DeepSeekChatClient", StopClient):
            records = [run_arm(row) for row in rows]
        self.assertEqual(library_hash("v4b"), original_hash)
        self.assertEqual({record["condition"] for record in records}, {"procedure_p0", "procedure_p1"})
        self.assertEqual({record["agent_protocol_version"] for record in records}, {"scienceworld-v14b"})
        self.assertEqual({record["shared_controller_version"] for record in records}, {"shared-state-checkpoint-v1"})
        self.assertEqual(len({prompt[0] for prompt in StopClient.prompts}), 1)
        for row, record, prompts in zip(rows, records, StopClient.prompts):
            self.assertEqual(record["skill_prompt_sha256"], row["skill_prompt_sha256"])
            self.assertIn(row["skill_name"], prompts[1])

    def test_resume_rejects_changed_protocol(self):
        row = plan()[0]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            path.write_text(json.dumps({
                "run_id": "dev", "task_name": row["task_name"], "variation": row["variation"],
                "repeat": row["repeat"], "condition": row["condition"], "model": "other-model",
            }) + "\n", encoding="utf-8")
            key = (row["task_name"], row["variation"], row["repeat"], row["condition"])
            with self.assertRaises(ValueError):
                existing_records(path, "dev", {key: row})


if __name__ == "__main__":
    unittest.main()
