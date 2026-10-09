"""Contract tests for the optional LM training data and actual tool rewards."""
import copy
import json
import tempfile
import unittest
import sys
from pathlib import Path

PLATFORM_SOURCE = Path(__file__).resolve().parents[2] / "byte-agent-platform" / "src"
sys.path.insert(0, str(PLATFORM_SOURCE))
from byte_agent.domain import create_dataset
from byte_agent.knowledge import Knowledge
from byte_agent.tools import registry
from byte_eval.training.environment import ToolEpisode, demonstrations, load_partition, teacher_decision
from byte_eval.training.review import review_candidates
from byte_eval.training.runner import verify_download_receipt
from byte_eval.training.policy import file_hash


class TrainingEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest = create_dataset(self.root)
        self.knowledge = Knowledge(self.root / "index.sqlite")
        self.knowledge.ingest(self.root / "knowledge")
        self.tools = registry(self.knowledge, self.root / "metrics.sqlite")
        self.train, self.validation, self.held, self.partition = load_partition(self.root / "services.json")

    def tearDown(self):
        self.knowledge.db.close()
        self.temp.cleanup()

    def test_partition_is_frozen_and_disjoint(self):
        groups = [{task["id"] for task in group} for group in (self.train, self.validation, self.held)]
        self.assertEqual([len(group) for group in groups], [18, 6, 8])
        self.assertFalse(groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])
        self.assertEqual(self.partition["partition_hash"], load_partition(self.root / "services.json")[3]["partition_hash"])

    def test_demonstrations_never_use_holdout_or_validation(self):
        rows = demonstrations(self.train, self.tools)
        self.assertEqual(len(rows), 72)
        self.assertEqual({row["task_id"] for row in rows}, set(self.partition["training_ids"]))
        for task in self.held + self.validation:
            with self.assertRaises(ValueError):
                demonstrations([task], self.tools)
        with self.assertRaises(ValueError):
            teacher_decision(self.held[0])

    def test_prompt_does_not_read_gold_fields(self):
        task = copy.deepcopy(self.train[0])
        altered = copy.deepcopy(task)
        for field in ("status", "likely_cause", "recommendation", "expected_uncertainty", "thresholds", "error_rate", "expected_change_kind"):
            altered[field] = "PRIVATE_GOLD_SENTINEL"
        first, second = ToolEpisode(task, self.tools), ToolEpisode(altered, self.tools)
        for action in "ABC":
            self.assertEqual(first.prompt(), second.prompt())
            first.step(action)
            second.step(action)
        self.assertEqual(first.prompt(), second.prompt())
        self.assertNotIn("PRIVATE_GOLD_SENTINEL", second.prompt())
        self.assertIn("Policy=", first.prompt())

    def test_actual_tools_and_correct_decision_earn_terminal_reward(self):
        for task in self.train + self.validation:
            episode = ToolEpisode(task, self.tools)
            for code in "ABC" + teacher_decision(task):
                episode.step(code)
            result = episode.finish()
            self.assertTrue(result["score"]["success"], (task["id"], result["score"]["checks"]))
            self.assertEqual(result["reward"], 1.3)
            self.assertEqual(len(result["trace"]["events"]), 3)

    def test_guess_without_execution_cannot_earn_tool_or_success_reward(self):
        task = self.train[0]
        episode = ToolEpisode(task, self.tools)
        episode.step(teacher_decision(task))
        result = episode.finish()
        self.assertFalse(result["score"]["success"])
        self.assertEqual(result["trace"]["events"], [])
        self.assertLess(result["reward"], 0)

    def test_repeated_tools_and_budget_are_penalized(self):
        episode = ToolEpisode(self.train[0], self.tools)
        for code in "AAAA":
            episode.step(code)
        result = episode.finish()
        self.assertEqual(result["trace"]["status"], "budget_exceeded")
        self.assertEqual(result["reward"], -0.7)
        with self.assertRaises(ValueError):
            episode.step("B")

    def test_operator_arguments_always_scope_service(self):
        episode = ToolEpisode(self.train[0], self.tools)
        for code in "ABC":
            episode.step(code)
        self.assertTrue(all(event["arguments"]["service"] == self.train[0]["service"] for event in episode.events))
        self.assertEqual(episode.events[0]["arguments"]["window_minutes"], 30)


class CandidateReviewTests(unittest.TestCase):
    def test_public_eight_candidates_are_technically_revalidated_not_human_reviewed(self):
        examples = Path(__file__).resolve().parents[1] / "examples" / "experiments"
        report = review_candidates([examples / "release-dev", examples / "release-verified-dev"])
        self.assertEqual(report["count"], 8)
        self.assertEqual(report["technical_passes"], 8)
        self.assertFalse(report["human_review_complete"])
        self.assertTrue(all(row["human_review_required"] and not row["included_in_tiny_policy_training"] for row in report["candidates"]))

    def test_pinned_receipt_checks_repository_revision_and_weight_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            weights = root / "model.safetensors"
            weights.write_bytes(b"unit-test weights, not a training artifact")
            receipt = {"repository": "example/model", "revision": "0"*40,
                       "files": {weights.name: {"sha256": file_hash(weights), "bytes": weights.stat().st_size}}}
            (root / "download-manifest.json").write_text(json.dumps(receipt), encoding="utf-8")
            self.assertEqual(verify_download_receipt(root, "example/model", "0"*40)["verified_files"], 1)
            with self.assertRaises(ValueError):
                verify_download_receipt(root, "different/model", "0"*40)
            weights.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                verify_download_receipt(root, "example/model", "0"*40)


if __name__ == "__main__":
    unittest.main()
