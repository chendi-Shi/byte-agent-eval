import hashlib
import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from byte_eval.experiment import run_suite, report, export_sft
from byte_eval.scoring import score
from test_eval import TASK, trace

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT.parent / "byte-agent-platform"


@contextmanager
def temporary_directory():
    # Inherit workspace permissions: owner-only tempfile ACLs are inaccessible
    # to a restricted Windows test process on some managed desktop hosts.
    parent = (ROOT / "runs").resolve()
    parent.mkdir(exist_ok=True)
    directory = parent / ("unittest-" + uuid.uuid4().hex)
    directory.mkdir()
    try:
        yield str(directory)
    finally:
        if not directory.resolve().is_relative_to(parent):
            raise ValueError("test cleanup escaped runs directory")
        shutil.rmtree(directory)


def dump(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def candidate_fixture(root):
    """A synthetic unit-test input marked real only to exercise exporter guards, never published as data."""
    t = trace()
    dump(root / "trace.json", t)
    result = {**score(TASK, t), "split": "dev", "task_id": TASK["id"], "profile": "grounded", "trial": 0,
              "config_hash": "hash", "trace_path": "trace.json", "available_tools": list(TASK["required_tools"]),
              "trace_sha256": hashlib.sha256((root / "trace.json").read_bytes()).hexdigest()}
    dump(root / "experiment.json", {"config_hash": "hash", "tasks": [TASK]})
    dump(root / "results.json", [result])
    return result


class SftGuardTests(unittest.TestCase):
    def test_filters_fixtures_holdout_failures_and_duplicate_messages(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            base = candidate_fixture(root)
            dump(root / "results.json", [base, {**base, "fixture": True}, {**base, "split": "holdout"},
                                         {**base, "success": False}, {**base, "profile": "baseline"}])
            result = export_sft(root, root / "sft.jsonl")
            self.assertEqual(1, result["exported"])
            row = json.loads((root / "sft.jsonl").read_text())
            self.assertTrue(row["metadata"]["human_review_required"])

    def test_portable_paths_survive_experiment_copy(self):
        with temporary_directory() as temporary:
            parent = Path(temporary)
            source = parent / "source"
            source.mkdir()
            candidate_fixture(source)
            moved = parent / "copied"
            shutil.copytree(source, moved)
            self.assertEqual(1, export_sft(moved, moved / "sft.jsonl")["exported"])

    def test_checksum_and_independent_oracle_reject_changed_trace(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            row = candidate_fixture(root)
            changed = trace()
            answer = json.loads(changed["answer"])
            answer["likely_cause"] = "dependency_outage"
            changed["answer"] = json.dumps(answer)
            dump(root / "trace.json", changed)
            with self.assertRaisesRegex(ValueError, "checksum"):
                export_sft(root, root / "sft.jsonl")
            row["trace_sha256"] = hashlib.sha256((root / "trace.json").read_bytes()).hexdigest()
            dump(root / "results.json", [row])
            with self.assertRaisesRegex(ValueError, "re-validation"):
                export_sft(root, root / "sft.jsonl")

    def test_absolute_and_escaping_paths_rejected(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            row = candidate_fixture(root)
            for reference in [str((root / "trace.json").resolve()), "../outside.json"]:
                dump(root / "results.json", [{**row, "trace_path": reference}])
                with self.assertRaises(ValueError):
                    export_sft(root, root / "sft.jsonl")

    def test_holdout_label_inside_manifest_cannot_be_forged_by_result(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            candidate_fixture(root)
            dump(root / "experiment.json", {"config_hash": "hash", "tasks": [{**TASK, "split": "holdout"}]})
            with self.assertRaisesRegex(ValueError, "re-validation"):
                export_sft(root, root / "sft.jsonl")


@unittest.skipUnless((PLATFORM / "src/byte_agent/domain.py").exists(), "sibling platform v2 required")
class SuiteIntegrationTests(unittest.TestCase):
    def test_entire_fixture_suite_and_dev_holdout_service_isolation(self):
        raw = json.loads((ROOT / "benchmarks/tasks.json").read_text(encoding="utf-8"))
        tasks = raw["tasks"]
        dev = {t["service"] for t in tasks if t["split"] == "dev"}
        holdout = {t["service"] for t in tasks if t["split"] == "holdout"}
        self.assertEqual((24, 8), (len(dev), len(holdout)))
        self.assertFalse(dev & holdout)
        with temporary_directory() as temporary:
            for split, count in (("dev", 24), ("holdout", 8)):
                directory = Path(temporary) / split
                rows = run_suite(ROOT / "benchmarks/tasks.json", PLATFORM, directory, fixture=True, split=split)
                self.assertEqual(count * 3, len(rows))
                for row in rows:
                    self.assertTrue(row["fixture"])
                    self.assertEqual(row["profile"] != "no-changes", row["success"], row)
                    self.assertFalse(Path(row["trace_path"]).is_absolute())
                summary = report(directory, True)
                self.assertTrue(summary["complete"])
                self.assertEqual(0, summary["paired"]["delta"])
                self.assertEqual(0, export_sft(directory, directory / "sft.jsonl")["exported"])
                self.assertEqual({}, report(directory)["groups"])

    def test_resume_is_idempotent_and_changed_configuration_rejected(self):
        with temporary_directory() as temporary:
            rows = run_suite(ROOT / "benchmarks/tasks.json", PLATFORM, temporary, fixture=True, limit=1)
            repeated = run_suite(ROOT / "benchmarks/tasks.json", PLATFORM, temporary, fixture=True, limit=1)
            self.assertEqual(rows, repeated)
            with self.assertRaisesRegex(ValueError, "configuration changed"):
                run_suite(ROOT / "benchmarks/tasks.json", PLATFORM, temporary, fixture=True, limit=1, seed=9)

    def test_provider_uncertain_stops_and_reports_unfinished_pairs(self):
        sys.path.insert(0, str(PLATFORM / "src"))
        import byte_agent.model
        with temporary_directory() as temporary:
            with patch.object(byte_agent.model.Ollama, "describe", return_value={"digest": "test", "ollama": {"version": "test"}}), \
                 patch.object(byte_agent.model.Ollama, "complete", side_effect=TimeoutError("unit-test provider failure")) as mocked:
                rows = run_suite(ROOT / "benchmarks/tasks.json", PLATFORM, temporary, model="test", limit=2, timeout=1)
            self.assertEqual(1, mocked.call_count)
            self.assertEqual(1, len(rows))
            self.assertEqual("uncertain", rows[0]["run_status"])
            self.assertGreater(rows[0]["unknown_usage"], 0)
            summary = report(temporary)
            self.assertFalse(summary["complete"])
            self.assertEqual(5, len(summary["missing_trials"]))
            self.assertEqual(1, summary["paired"]["missing_pair_trials"])
            self.assertIn("INCOMPLETE", (Path(temporary) / "report.md").read_text(encoding="utf-8"))

    def test_selection_guards_and_explicit_ablation_tool_sets(self):
        with temporary_directory() as temporary:
            for kwargs in ({"trials": 0}, {"task_ids": ["holdout-comment"]}, {"profiles": ["grounded", "grounded"]}):
                with self.assertRaises(ValueError):
                    run_suite(ROOT / "benchmarks/tasks.json", PLATFORM, temporary, fixture=True, **kwargs)
            rows = run_suite(ROOT / "benchmarks/tasks.json", PLATFORM, temporary, fixture=True, task_ids=["growth-feed"])
            self.assertEqual(3, len(rows))
            tool_sets = {r["profile"]: set(r["available_tools"]) for r in rows}
            self.assertEqual(tool_sets["baseline"], tool_sets["grounded"])
            self.assertEqual(tool_sets["grounded"] - {"incident_changes"}, tool_sets["no-changes"])
