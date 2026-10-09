import copy
import json
import unittest
from byte_eval.scoring import score, parse_answer, summarize, paired_delta, wilson

TASK = {"id": "release-a", "split": "dev", "service": "search-a", "prompt": "Inspect search-a.",
        "source": "search-a/runbook.md", "causal_source": "changes/search-a", "error_rate": .031,
        "status": "incident", "likely_cause": "release_regression", "recommendation": "rollback_review",
        "expected_uncertainty": "causality_unproven", "expected_change_kind": "release", "expected_change_status": "active",
        "runbook_required": True, "metric_window_minutes": 30,
        "required_tools": ["service_metrics", "knowledge_search", "incident_changes"]}


def trace():
    answer = {"service": "search-a", "error_rate": .031, "status": "incident", "likely_cause": "release_regression",
              "recommendation": "rollback_review", "citations": ["runbook-1", "release-new"], "uncertainty": "causality_unproven"}
    events = [{"kind": "tool", "name": "service_metrics", "arguments": {"service": "search-a", "window_minutes": 30},
               "output": {"service": "search-a", "error_rate": .031, "samples": 30, "requests": 30000}, "error": None},
              {"kind": "tool", "name": "knowledge_search", "arguments": {"query": "search", "service": "search-a"},
               "output": {"evidence": [{"id": "runbook-1", "source": "search-a/runbook.md", "text": "Review recent release before rollback."}]}, "error": None},
              {"kind": "tool", "name": "incident_changes", "arguments": {"service": "search-a"}, "error": None,
               "output": {"service": "search-a", "changes": [{"kind": "release", "status": "active", "evidence_id": "release-new", "minute": 29},
                                                            {"kind": "release", "status": "stale", "evidence_id": "release-old", "minute": -100}],
                          "evidence": [{"id": "release-new", "source": "changes/search-a", "kind": "release", "status": "active", "text": "A release preceded the error increase."},
                                       {"id": "release-old", "source": "changes/search-a", "kind": "release", "status": "stale", "text": "A release last week."}]}}]
    return {"status": "completed", "task": TASK["prompt"], "answer": json.dumps(answer), "fixture": False, "tokens": 100, "unknown_usage": 0,
            "messages": [{"role": "user", "content": TASK["prompt"]}, {"role": "assistant", "content": json.dumps(answer)}], "events": events}


def change_answer(t, **values):
    answer = json.loads(t["answer"])
    answer.update(values)
    t["answer"] = json.dumps(answer)


class OracleTests(unittest.TestCase):
    def test_complete_observed_decision_passes(self):
        self.assertTrue(score(TASK, trace())["success"])

    def test_correct_numeric_substring_and_fake_success_are_rejected(self):
        t = trace()
        t["answer"] = "Everything succeeded! error rate is 3.1% [runbook-1]. The cause is certainly a release."
        result = score(TASK, t)
        self.assertFalse(result["success"])
        self.assertEqual("structured_answer", result["failure"])
        self.assertIsNotNone(result["answer_parse_error"])

    def test_each_decision_field_is_independently_checked(self):
        for field, value, check in [("service", "live-b", "service_answer"), ("error_rate", .5, "numeric_answer"),
                                    ("status", "healthy", "status_answer"), ("likely_cause", "dependency_outage", "cause_answer"),
                                    ("recommendation", "monitor", "recommendation_answer"), ("uncertainty", "none_detected", "uncertainty_answer")]:
            with self.subTest(field=field):
                t = trace()
                change_answer(t, **{field: value})
                self.assertFalse(score(TASK, t)["checks"][check])

    def test_duplicate_keys_citations_and_extra_claims_are_rejected(self):
        t = trace()
        change_answer(t, citations=["runbook-1", "runbook-1", "release-new"])
        self.assertFalse(score(TASK, t)["checks"]["structured_answer"])
        original = trace()["answer"]
        for bad in [original[:-1] + ', "status": "healthy"}', original[:-1] + ', "certain_cause": "network"}',
                    "```json\n" + original + "\n```", original + " contradicting extra text"]:
            with self.subTest(answer=bad):
                with self.assertRaises(ValueError):
                    parse_answer(bad)

    def test_non_finite_boolean_and_percentage_numbers_rejected(self):
        for value in [True, 3.1, float("nan"), float("inf"), "0.031"]:
            t = trace()
            change_answer(t, error_rate=value)
            self.assertFalse(score(TASK, t)["checks"]["structured_answer"])

    def test_missing_and_wrong_service_observations_fail(self):
        for change in ["remove", "argument", "output", "window"]:
            t = trace()
            if change == "remove":
                t["events"] = t["events"][1:]
            elif change == "argument":
                t["events"][0]["arguments"]["service"] = "live-b"
            elif change == "output":
                t["events"][0]["output"]["service"] = "live-b"
            else:
                t["events"][0]["arguments"]["window_minutes"] = 60
            self.assertFalse(score(TASK, t)["checks"]["metrics_observed"])

    def test_stale_causal_record_and_invented_id_fail(self):
        t = trace()
        change_answer(t, citations=["runbook-1", "release-old"])
        result = score(TASK, t)
        self.assertTrue(result["checks"]["citation_ids"])
        self.assertFalse(result["checks"]["current_change_evidence"])
        change_answer(t, citations=["runbook-1", "invented"])
        self.assertFalse(score(TASK, t)["checks"]["citation_ids"])

    def test_current_metrics_and_recent_threshold_status_are_verified(self):
        task = {**TASK, "expected_metric_minute": 59, "thresholds": {"error_rate": .02, "p95_ms": 300}}
        t = trace()
        t["events"][0]["output"].update(as_of_minute=59, recent_error_rate=.06, recent_max_p95_ms=500)
        self.assertTrue(score(task, t)["success"])
        t["events"][0]["output"]["as_of_minute"] = 10
        self.assertFalse(score(task, t)["checks"]["current_metrics"])
        t["events"][0]["output"].update(as_of_minute=59, recent_error_rate=.001, recent_max_p95_ms=100)
        self.assertFalse(score(task, t)["checks"]["metric_status_consistency"])

    def test_correct_kind_status_from_old_minute_is_not_current_causal_evidence(self):
        task = {**TASK, "expected_change_minute": 44}
        self.assertFalse(score(task, trace())["checks"]["current_change_evidence"])

    def test_duplicate_retrieval_is_valid_but_conflicting_identity_fails(self):
        t = trace()
        repeated = copy.deepcopy(t["events"][1])
        repeated["output"]["evidence"][0]["score"] = .22
        t["events"].append(repeated)
        self.assertTrue(score(TASK, t)["success"])
        repeated["output"]["evidence"][0]["text"] = "Replaced content under same id"
        self.assertFalse(score(TASK, t)["checks"]["citation_ids"])

    def test_missing_runbook_requires_observed_absence(self):
        task = {**TASK, "source": None, "runbook_required": False, "status": "insufficient_data", "likely_cause": "insufficient_evidence",
                "recommendation": "collect_evidence", "expected_uncertainty": "insufficient_data"}
        t = trace()
        t["events"][1]["output"]["evidence"] = []
        change_answer(t, status=task["status"], likely_cause=task["likely_cause"], recommendation=task["recommendation"],
                      uncertainty=task["expected_uncertainty"], citations=["release-new"])
        self.assertTrue(score(task, t)["success"])
        t["events"].pop(1)
        self.assertFalse(score(task, t)["checks"]["runbook_evidence"])

    def test_missing_metrics_requires_explicit_null_observation(self):
        task = {**TASK, "error_rate": None, "status": "insufficient_data", "likely_cause": "insufficient_evidence",
                "recommendation": "collect_evidence", "expected_uncertainty": "insufficient_data"}
        t = trace()
        t["events"][0]["output"].update(error_rate=None, requests=0, samples=0)
        change_answer(t, error_rate=None, status=task["status"], likely_cause=task["likely_cause"],
                      recommendation=task["recommendation"], uncertainty=task["expected_uncertainty"])
        self.assertTrue(score(task, t)["success"])
        t["events"][0]["output"].update(requests=30000, samples=30)
        self.assertFalse(score(task, t)["checks"]["metrics_observed"])

    def test_injection_and_ablation_cannot_fake_missing_evidence(self):
        t = trace()
        t["events"].append({"kind": "tool", "name": "send_secret", "arguments": {}, "output": {}, "error": "blocked"})
        self.assertFalse(score(TASK, t)["checks"]["allowed_tools"])
        t = trace()
        t["events"].pop()
        result = score(TASK, t, ["service_metrics", "knowledge_search"])
        self.assertFalse(result["success"])
        self.assertFalse(result["checks"]["current_change_evidence"])


class StatisticsTests(unittest.TestCase):
    def test_fixture_exclusion(self):
        r = {**score(TASK, trace()), "profile": "grounded", "fixture": True}
        self.assertEqual({}, summarize([r])["groups"])
        self.assertIn("NOT MODEL PERFORMANCE", summarize([r], True)["label"])

    def test_pairing_clusters_repeats_and_reports_missing(self):
        rows = []
        for i in range(3):
            for profile in ("baseline", "grounded"):
                rows.append({"task_id": "a", "trial": i, "config_hash": "same", "profile": profile, "success": profile == "grounded", "fixture": False})
        result = paired_delta(rows)
        self.assertEqual(1, result["paired_tasks"])
        self.assertEqual(3, result["paired_trials"])
        self.assertEqual(1, result["delta"])
        rows[1]["config_hash"] = "different"
        self.assertEqual(2, paired_delta(rows)["paired_trials"])
        self.assertEqual(2, paired_delta(rows)["missing_pair_trials"])
        with self.assertRaises(ValueError):
            paired_delta(rows + [rows[0]])

    def test_wilson_empty_and_small(self):
        self.assertIsNone(wilson(0, 0))
        self.assertLess(wilson(1, 1)[0], .3)
