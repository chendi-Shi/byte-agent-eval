"""Malformed numeric/JSON answers must be scored failures, not suite crashes."""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1] if (HERE / "byte_eval").is_dir() else HERE
sys.path.insert(0, str(HERE if (HERE / "byte_eval").is_dir() else ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from byte_eval.scoring import parse_answer, score
from test_eval import TASK, trace


class ScoringBoundaryTests(unittest.TestCase):
    def test_huge_integer_final_answer_is_a_regular_format_failure(self):
        t = trace()
        answer = json.loads(t["answer"])
        answer["error_rate"] = 10 ** 400
        t["answer"] = json.dumps(answer)
        result = score(TASK, t)
        self.assertFalse(result["success"])
        self.assertEqual("structured_answer", result["failure"])
        self.assertIsNotNone(result["answer_parse_error"])

    def test_huge_integer_tool_measurement_is_a_regular_observation_failure(self):
        t = trace()
        t["events"][0]["output"]["error_rate"] = 10 ** 400
        result = score(TASK, t)
        self.assertFalse(result["success"])
        self.assertFalse(result["checks"]["metrics_observed"])

    def test_deep_json_is_reported_as_parse_failure_not_recursion_crash(self):
        t = trace()
        t["answer"] = "[" * 2000 + "0" + "]" * 2000
        result = score(TASK, t)
        self.assertFalse(result["success"])
        self.assertIsNotNone(result["answer_parse_error"])

    def test_valid_answer_and_six_decimal_tolerance_are_unchanged(self):
        t = trace()
        self.assertTrue(score(TASK, t)["success"])
        answer = json.loads(t["answer"])
        answer["error_rate"] += 0.0000005
        t["answer"] = json.dumps(answer)
        self.assertTrue(score(TASK, t)["success"])


if __name__ == "__main__":
    unittest.main()
