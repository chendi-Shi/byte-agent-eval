import json
import tempfile
import unittest
import sys
from unittest.mock import patch
from pathlib import Path
from byte_eval.scoring import score, summarize, paired_delta, wilson
from byte_eval.experiment import export_sft
from byte_eval.experiment import run_suite


TASK = {"service": "search", "source": "search.md", "error_rate": .05}


def trace():
    return {"status": "completed", "task": "task", "answer": "5% [abc]", "fixture": False, "tokens": 100, "unknown_usage": 0,
            "messages": [{"role": "user", "content": "task"}, {"role": "assistant", "content": "5% [abc]"}],
            "events": [{"kind": "tool", "name": "service_metrics", "arguments": {"service": "search"}, "output": {"error_rate": .05}, "error": None},
                       {"kind": "tool", "name": "knowledge_search", "arguments": {"query": "search"}, "output": {"evidence": [{"id": "abc", "source": "search.md"}]}, "error": None}]}


class EvalTests(unittest.TestCase):
    def test_oracle_rejects_invented_success(self):
        t = trace()
        self.assertTrue(score(TASK, t)["success"])
        t["answer"] = "Everything succeeded! 50% [invented]"
        self.assertFalse(score(TASK, t)["success"])
        self.assertFalse(score(TASK, t)["checks"]["citation"])

    def test_wrong_service_does_not_pass(self):
        t = trace()
        t["events"][0]["arguments"]["service"] = "live"
        self.assertFalse(score(TASK, t)["checks"]["metrics_observed"])

    def test_duplicate_evidence_and_invented_extra_citation(self):
        t = trace()
        t["events"].append(t["events"][1])
        self.assertEqual(1, score(TASK, t)["citation_precision"])
        t["answer"] += " [invented]"
        self.assertFalse(score(TASK, t)["checks"]["citation"])

    def test_injection_attempt_fails_safety(self):
        t = trace()
        t["events"].append({"kind": "tool", "name": "send_secret", "arguments": {}, "output": {}, "error": "blocked"})
        self.assertFalse(score(TASK, t)["checks"]["allowed_tools"])

    def test_fixture_exclusion(self):
        r = {**score(TASK, trace()), "profile": "grounded", "fixture": True}
        self.assertEqual({}, summarize([r])["groups"])
        self.assertIn("NOT MODEL PERFORMANCE", summarize([r], True)["label"])

    def test_pairing_and_cluster_bootstrap(self):
        rows = []
        for i in range(3):
            for profile in ("baseline", "grounded"):
                rows.append({"task_id": "a", "trial": i, "config_hash": "same", "profile": profile, "success": profile == "grounded", "fixture": False})
        result = paired_delta(rows)
        self.assertEqual(1, result["paired_tasks"])
        self.assertEqual(1, result["delta"])
        rows[1]["config_hash"] = "different"
        self.assertEqual(1, paired_delta(rows)["paired_tasks"])
        with self.assertRaises(ValueError):
            paired_delta(rows + [rows[0]])

    def test_wilson_empty_and_small(self):
        self.assertIsNone(wilson(0, 0))
        self.assertLess(wilson(1, 1)[0], .3)

    def test_provider_uncertain_stops_further_tasks(self):
        platform = Path(__file__).resolve().parents[2] / "byte-agent-platform"
        if not platform.exists():
            self.skipTest("sibling platform required for integration check")
        sys.path.insert(0, str(platform / "src"))
        import byte_agent.runtime
        import byte_agent.model
        failed = {**trace(), "status": "uncertain", "answer": "", "events": [], "unknown_usage": 1}
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(byte_agent.model.Ollama, "describe", return_value={"digest": "test"}), patch.object(byte_agent.runtime.Runtime, "run", return_value=failed) as mocked:
                results = run_suite(Path(__file__).resolve().parents[1] / "benchmarks/tasks.json", platform, temporary, model="test")
            self.assertEqual(1, mocked.call_count)
            self.assertEqual(1, len(results))
            self.assertTrue((Path(temporary) / "results.json").exists())
            self.assertEqual("provider_uncertain", json.loads((Path(temporary) / "interrupted.json").read_text())["reason"])

    def test_sft_filters_fixtures_holdout_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "trace.json"
            path.write_text(json.dumps(trace()), encoding="utf-8")
            base = {"fixture": False, "success": True, "split": "dev", "trace_path": str(path), "task_id": "a", "config_hash": "hash"}
            rows = [base, {**base, "fixture": True}, {**base, "split": "holdout"}, {**base, "success": False}]
            (root / "results.json").write_text(json.dumps(rows), encoding="utf-8")
            (root / "experiment.json").write_text(json.dumps({"config_hash": "hash", "tasks": [{**TASK, "id": "a", "split": "dev", "prompt": "task"}]}), encoding="utf-8")
            result = export_sft(root, root / "sft.jsonl")
            self.assertEqual(1, result["exported"])
            self.assertEqual(1, len((root / "sft.jsonl").read_text(encoding="utf-8").splitlines()))
            changed = trace()
            changed["answer"] = "fake success"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(ValueError):
                export_sft(root, root / "sft.jsonl")


if __name__ == "__main__":
    unittest.main()
