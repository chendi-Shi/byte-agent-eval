"""Tests of isolated verified treatment; fixtures never count as model performance."""
import copy
import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

STAGE = Path(__file__).resolve().parents[1]
IS_STAGED = (STAGE / "byte_eval").is_dir()
ROOT = STAGE.parents[1] if IS_STAGED else STAGE
PLATFORM = ROOT.parent / ("byte-agent-platform/runs/fix-verified-platform" if IS_STAGED else "byte-agent-platform")
sys.path.insert(0, str(STAGE if IS_STAGED else ROOT / "src"))
from byte_eval.experiment import run_suite, report, export_sft, PROFILES
import byte_eval.experiment as experiment
import byte_eval.cli as cli


@contextmanager
def output_directory():
    parent = (ROOT / "runs").resolve()
    directory = parent / ("verified-unittest-" + uuid.uuid4().hex)
    directory.mkdir()
    try:
        yield directory
    finally:
        if not directory.resolve().is_relative_to(parent):
            raise ValueError("unsafe test cleanup")
        shutil.rmtree(directory)


class VerifiedIntegrationTests(unittest.TestCase):
    def test_all_32_cases_verified_fixture_scopes_and_callback_are_recorded(self):
        with output_directory() as parent:
            for split, count in (("dev", 24), ("holdout", 8)):
                directory = parent / split
                rows = run_suite(ROOT / "benchmarks/tasks.json", PLATFORM, directory, fixture=True, split=split, profiles=["verified"])
                self.assertEqual(count, len(rows))
                self.assertTrue(all(r["success"] for r in rows), rows)
                self.assertTrue(all(r["fixture"] and r["validation_attempts"] == 1 and r["validation_rejections"] == 0 for r in rows))
                manifest = json.loads((directory / "experiment.json").read_text(encoding="utf-8"))
                profile = manifest["profiles"]["verified"]
                self.assertEqual("tool_scope_and_output_validation", profile["kind"])
                self.assertFalse(profile["verification_rules"]["gold_labels_read"])
                revisions = set()
                for task in manifest["tasks"]:
                    revisions.add(profile["validator_revisions"][task["id"]])
                    for item in profile["task_tool_specs"][task["id"]]:
                        schema = item["spec"]["inputSchema"]
                        self.assertEqual([task["service"]], schema["properties"]["service"]["enum"])
                        self.assertIn("service", schema["required"])
                self.assertEqual(count, len(revisions))
                summary = report(directory, include_fixtures=True)
                self.assertTrue(summary["complete"])
                self.assertNotIn("paired", summary)
                self.assertNotIn("causal_tool_ablation", summary)
                self.assertEqual(count, summary["verified_treatment"]["validation_attempts"])
                self.assertIn("not a pure prompt comparison", (directory / "report.md").read_text(encoding="utf-8"))
                self.assertEqual(0, export_sft(directory, directory / "candidates.jsonl")["exported"])

    def test_wrong_recent_aggregate_is_repaired_by_one_bounded_model_step(self):
        original = experiment._fixture
        def erroneous(task, tools, scripted):
            agent = original(task, tools, scripted)
            correct = copy.deepcopy(agent.decisions[-1])
            wrong = json.loads(agent.decisions[-1]["answer"])
            wrong["error_rate"] = tools["service_metrics"].call({"service": task["service"], "window_minutes": 30})["recent_error_rate"]
            agent.decisions[-1]["answer"] = json.dumps(wrong)
            agent.decisions.append(correct)
            return agent
        with output_directory() as output:
            with patch.object(experiment, "_fixture", side_effect=erroneous):
                rows = run_suite(ROOT / "benchmarks/tasks.json", PLATFORM, output, fixture=True, task_ids=["creator-upload"], profiles=["verified"])
            self.assertTrue(rows[0]["success"])
            self.assertEqual((2, 1), (rows[0]["validation_attempts"], rows[0]["validation_rejections"]))
            trace = json.loads((output / rows[0]["trace_path"]).read_text(encoding="utf-8"))
            self.assertEqual(3, trace["steps"])
            self.assertEqual(3, trace["calls"])
            self.assertEqual([False, True], [e["valid"] for e in trace["events"] if e["kind"] == "validation"])

    def test_repair_respects_original_step_budget(self):
        original = experiment._fixture
        def malformed(task, tools, scripted):
            agent = original(task, tools, scripted)
            corrected = copy.deepcopy(agent.decisions[-1])
            agent.decisions[-1]["answer"] = "not JSON"
            agent.decisions.append(corrected)
            return agent
        with output_directory() as output:
            with patch.object(experiment, "_fixture", side_effect=malformed):
                rows = run_suite(ROOT / "benchmarks/tasks.json", PLATFORM, output, fixture=True, limit=1, profiles=["verified"], max_steps=2)
            self.assertFalse(rows[0]["success"])
            self.assertEqual("budget_exceeded", rows[0]["run_status"])
            self.assertEqual(1, rows[0]["validation_rejections"])

    def test_wrong_service_is_blocked_and_remains_a_strict_failure(self):
        original = experiment._fixture
        def wrong_service(task, tools, scripted):
            agent = original(task, tools, scripted)
            agent.decisions[0]["calls"][0]["arguments"]["service"] = "different-service"
            return agent
        with output_directory() as output:
            with patch.object(experiment, "_fixture", side_effect=wrong_service):
                rows = run_suite(ROOT / "benchmarks/tasks.json", PLATFORM, output, fixture=True, limit=1, profiles=["verified"])
            self.assertFalse(rows[0]["success"])
            self.assertEqual("validation_failed", rows[0]["run_status"])
            trace = json.loads((output / rows[0]["trace_path"]).read_text(encoding="utf-8"))
            metric = next(e for e in trace["events"] if e.get("kind") == "tool" and e.get("name") == "service_metrics")
            self.assertEqual("ValueError", metric["error"])
            self.assertNotIn("error_rate", metric["output"])

    def test_default_profiles_remain_original_three_and_verified_is_explicit(self):
        self.assertIn("verified", PROFILES)
        with patch.object(sys, "argv", ["byte_eval", "run", "--fixture"]), patch.object(cli, "run_suite", return_value=[]) as run:
            cli.main()
            self.assertEqual(["baseline", "grounded", "no-changes"], run.call_args.kwargs["profiles"])
        with patch.object(sys, "argv", ["byte_eval", "run", "--fixture", "--profiles", "verified"]), patch.object(cli, "run_suite", return_value=[]) as run:
            cli.main()
            self.assertEqual(["verified"], run.call_args.kwargs["profiles"])

    def test_ordinary_profiles_do_not_require_new_runtime_keyword(self):
        sys.path.insert(0, str(PLATFORM / "src"))
        from byte_agent.runtime import Runtime, SYSTEM
        original = Runtime.__init__
        seen = []
        # This constructor accepts the frozen platform's interface, without answer_validator.
        def legacy_init(instance, directory, model, tools, max_steps=8, max_calls=16, max_tokens=12000, max_context=60000, system_prompt=SYSTEM):
            seen.append(system_prompt)
            original(instance, directory, model, tools, max_steps, max_calls, max_tokens, max_context, system_prompt)
        with output_directory() as output:
            with patch.object(Runtime, "__init__", legacy_init):
                rows = run_suite(ROOT / "benchmarks/tasks.json", PLATFORM, output, fixture=True, limit=1)
            self.assertEqual({"baseline", "grounded", "no-changes"}, {r["profile"] for r in rows})
            self.assertEqual(3, len(seen))


if __name__ == "__main__":
    unittest.main()
