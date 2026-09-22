"""The offline audit must check each suite against its declared split."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scienceworld_retrieval_audit


class RetrievalAuditSplitTest(unittest.TestCase):
    def test_uses_declared_split_without_starting_scienceworld(self):
        class FakeEnv:
            def __init__(self, expected_split):
                self.expected_split = expected_split
                self.variation = None

            def load(self, _task_name, variationIdx, simplificationStr):
                self.variation = variationIdx

            def reset(self):
                return "", {"taskDesc": "Find the task target."}

            def close(self):
                pass

            def __getattr__(self, name):
                if name == f"get_variations_{self.expected_split}":
                    return lambda: [self.variation]
                raise AssertionError(f"wrong split lookup: {name}")

        cases = (
            ("scienceworld-pilot-6", "train", 6),
            ("scienceworld-v14-dev-4", "dev", 4),
            ("scienceworld-v3-heldout-6", "test", 6),
        )
        with tempfile.TemporaryDirectory() as directory:
            for suite, split, count in cases:
                with self.subTest(split=split):
                    output = Path(directory) / f"{split}.jsonl"
                    argv = ["audit", "--suite", suite, "--output", str(output)]
                    with patch("sys.argv", argv), patch.object(scienceworld_retrieval_audit, "make_env", return_value=FakeEnv(split)):
                        self.assertEqual(scienceworld_retrieval_audit.main(), 0)
                    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
                    self.assertEqual(len(rows), count)
                    self.assertEqual({row["variation_split"] for row in rows}, {split})


if __name__ == "__main__":
    unittest.main()
