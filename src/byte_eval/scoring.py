"""Independent structured decision oracle; never trusts an agent's success claim."""
import json
import math
import statistics

ALLOWED = {"knowledge_search", "service_metrics", "incident_changes"}
FIELDS = {"service", "error_rate", "status", "likely_cause", "recommendation", "citations", "uncertainty"}
STATUSES = {"healthy", "incident", "insufficient_data"}
CAUSES = {"none", "release_regression", "dependency_outage", "capacity_pressure", "insufficient_evidence", "conflicting_evidence"}
RECOMMENDATIONS = {"monitor", "rollback_review", "dependency_escalation", "capacity_review", "collect_evidence", "verify_changes"}
UNCERTAINTIES = {"none_detected", "causality_unproven", "insufficient_data", "conflicting_evidence"}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def parse_answer(answer):
    """Require one JSON object, exact fields and enums; prose/fences/NaN are invalid."""
    if not isinstance(answer, str):
        raise ValueError("answer must be JSON text")
    def invalid_constant(value):
        raise ValueError("non-finite JSON constant: " + value)
    try:
        obj = json.loads(answer, object_pairs_hook=_unique_object, parse_constant=invalid_constant)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("invalid JSON: " + str(exc)) from exc
    if not isinstance(obj, dict) or set(obj) != FIELDS:
        raise ValueError("answer must contain exactly: " + ", ".join(sorted(FIELDS)))
    if not isinstance(obj["service"], str) or not obj["service"]:
        raise ValueError("service must be a nonempty string")
    rate = obj["error_rate"]
    if rate is not None and (type(rate) not in (int, float) or not 0 <= rate <= 1 or not math.isfinite(rate)):
        raise ValueError("error_rate must be null or a finite fraction in [0,1]")
    for field, values in (("status", STATUSES), ("likely_cause", CAUSES), ("recommendation", RECOMMENDATIONS), ("uncertainty", UNCERTAINTIES)):
        if not isinstance(obj[field], str) or obj[field] not in values:
            raise ValueError("invalid " + field + " enum")
    ids = obj["citations"]
    if not isinstance(ids, list) or any(not isinstance(i, str) or not i or len(i) > 128 for i in ids):
        raise ValueError("citations must be an array of bounded evidence ids")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate citations")
    return obj


def _same_number(actual, expected):
    if expected is None:
        return actual is None
    # Absolute fraction tolerance accepts six-decimal reporting, not a wrong percentage scale.
    return type(actual) in (int, float) and 0 <= actual <= 1 and math.isfinite(actual) and math.isclose(actual, expected, abs_tol=1e-6, rel_tol=1e-6)


def score(task, trace, allowed_tools=None):
    allowed_tools = ALLOWED if allowed_tools is None else set(allowed_tools)
    calls = [e for e in trace.get("events", []) if e.get("kind") == "tool"]
    valid = [e for e in calls if not e.get("error") and isinstance(e.get("output"), dict) and "error" not in e["output"]]
    target = task["service"]
    def targeted(name):
        return [e for e in valid if e.get("name") == name and e.get("arguments", {}).get("service") == target]
    metrics = targeted("service_metrics")
    searches = targeted("knowledge_search")
    changes = targeted("incident_changes")
    window = task.get("metric_window_minutes", 30)
    observations = [e["output"] for e in metrics if e["arguments"].get("window_minutes", 30) == window and e["output"].get("service") == target]
    observed = any("error_rate" in o and _same_number(o["error_rate"], task["error_rate"]) for o in observations)
    if task["error_rate"] is None:
        observed = observed and any(o.get("samples", 0) == 0 or o.get("requests", 0) == 0 for o in observations)
    else:
        observed = observed and any(o.get("samples") == window and o.get("requests", 0) > 0 for o in observations)
    current_metrics = any(o.get("as_of_minute") == task.get("expected_metric_minute") for o in observations) if "expected_metric_minute" in task else observed
    thresholds = task.get("thresholds")
    status_supported = False
    for observation in observations:
        if task["error_rate"] is None or not task.get("runbook_required", bool(task.get("source"))):
            observed_status = "insufficient_data"
        elif thresholds and type(observation.get("recent_error_rate")) in (int, float) and type(observation.get("recent_max_p95_ms")) in (int, float):
            observed_status = "incident" if observation["recent_error_rate"] >= thresholds["error_rate"] or observation["recent_max_p95_ms"] > thresholds["p95_ms"] else "healthy"
        elif not thresholds:
            observed_status = task["status"]  # Allows handcrafted unit-test tasks without a policy threshold.
        else:
            continue
        status_supported = status_supported or observed_status == task["status"]
    evidence = {}
    identity_consistent = True
    for event in searches + changes:
        for item in event["output"].get("evidence", []):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                identity_consistent = False
                continue
            stable_fields = ("source", "text", "kind", "status", "minute")
            if item["id"] in evidence and any(evidence[item["id"]].get(f) != item.get(f) for f in stable_fields):
                identity_consistent = False
            evidence[item["id"]] = item
    parse_error = None
    try:
        answer = parse_answer(trace.get("answer", ""))
    except ValueError as exc:
        answer, parse_error = {}, str(exc)
    citations = answer.get("citations", [])
    cited = [evidence[c] for c in citations if c in evidence]
    expected_sources = {s for s in (task.get("source"), task.get("causal_source")) if s}
    references_valid = bool(citations) and len(cited) == len(citations) and identity_consistent and all(c.get("source") in expected_sources for c in cited)
    runbook_required = task.get("runbook_required", bool(task.get("source")))
    runbook_cited = any(c.get("source") == task.get("source") for c in cited) if runbook_required else bool(searches) and not any(e["output"].get("evidence") for e in searches)
    causal_ids = set()
    for e in changes:
        if e["output"].get("service") != target:
            continue
        for change in e["output"].get("changes", []):
            if change.get("kind") == task.get("expected_change_kind") and change.get("status") == task.get("expected_change_status") and ("expected_change_minute" not in task or change.get("minute") == task["expected_change_minute"]):
                if change.get("evidence_id"):
                    causal_ids.add(change["evidence_id"])
    causal_cited = any(c.get("id") in causal_ids and c.get("source") == task.get("causal_source") and c.get("kind") == task.get("expected_change_kind") and c.get("status") == task.get("expected_change_status") and ("expected_change_minute" not in task or c.get("minute") == task["expected_change_minute"]) for c in cited)
    required = set(task.get("required_tools", ALLOWED))
    names_observed = {e.get("name") for e in valid if e.get("arguments", {}).get("service") == target}
    checks = {
        "completed": trace.get("status") == "completed",
        "structured_answer": parse_error is None,
        "service_answer": answer.get("service") == target,
        "metrics_observed": observed,
        "current_metrics": current_metrics,
        "metric_status_consistency": status_supported,
        "numeric_answer": "error_rate" in answer and _same_number(answer["error_rate"], task["error_rate"]),
        "status_answer": answer.get("status") == task["status"],
        "cause_answer": answer.get("likely_cause") == task["likely_cause"],
        "recommendation_answer": answer.get("recommendation") == task["recommendation"],
        "uncertainty_answer": answer.get("uncertainty") == task["expected_uncertainty"],
        "citation_ids": references_valid,
        "runbook_evidence": runbook_cited,
        "current_change_evidence": causal_cited,
        "required_tools": required <= names_observed,
        "allowed_tools": all(e.get("name") in allowed_tools for e in calls),
        "no_tool_errors": len(valid) == len(calls),
        "service_scoped_calls": all(e.get("arguments", {}).get("service") == target for e in calls if e.get("name") in ALLOWED),
    }
    failure = next((name for name, passed in checks.items() if not passed), None)
    decision_checks = ("completed", "structured_answer", "service_answer", "numeric_answer", "status_answer", "cause_answer", "recommendation_answer", "uncertainty_answer")
    return {"success": all(checks.values()), "decision_correct": all(checks[c] for c in decision_checks), "checks": checks, "failure": failure,
            "answer_parse_error": parse_error, "parsed_answer": answer or None,
            "tool_execution_accuracy": len(valid) / len(calls) if calls else None,
            "citation_precision": sum(c.get("source") in expected_sources for c in cited) / len(citations) if citations else None,
            "tool_calls": len(calls), "latency_seconds": sum(e.get("seconds", 0) for e in trace.get("events", [])),
            "known_tokens": trace.get("tokens", 0), "unknown_usage": trace.get("unknown_usage", 0), "fixture": trace.get("fixture", False)}


def wilson(successes, count):
    if not count:
        return None
    if not 0 <= successes <= count:
        raise ValueError("invalid successes/count")
    z = 1.96
    p = successes / count
    center = (p + z*z / (2*count)) / (1 + z*z/count)
    half = z * math.sqrt(p*(1-p)/count + z*z/(4*count*count)) / (1 + z*z/count)
    return [max(0, center - half), min(1, center + half)]


def summarize(results, include_fixtures=False):
    selected = [r for r in results if include_fixtures or not r["fixture"]]
    groups = {}
    for profile in sorted({r["profile"] for r in selected}):
        rows = [r for r in selected if r["profile"] == profile]
        passed = sum(r["success"] for r in rows)
        failures = {f: sum(r["failure"] == f for r in rows) for f in sorted({r["failure"] for r in rows if r["failure"]})}
        latencies = [r.get("wall_seconds", r["latency_seconds"]) for r in rows]
        groups[profile] = {"trials": len(rows), "successes": passed, "success_rate": passed / len(rows),
                           "decision_accuracy": sum(r.get("decision_correct", False) for r in rows) / len(rows),
                           "decision_accuracy_definition": "Exact answer fields only; does not require observed/cited evidence or all required tools. Secondary metric, never replaces task success.",
                           "wilson95_descriptive": wilson(passed, len(rows)),
                           "known_tokens": sum(r["known_tokens"] for r in rows),
                           "unknown_usage_trials": sum(r["unknown_usage"] > 0 for r in rows),
                           "mean_tool_calls": statistics.mean(r["tool_calls"] for r in rows),
                           "median_wall_seconds": statistics.median(latencies),
                           "parse_failure_trials": sum(r.get("answer_parse_error") is not None for r in rows),
                           "check_failures": {check: sum(not r["checks"].get(check, False) for r in rows) for check in sorted({c for r in rows for c in r["checks"]})},
                           "failures": failures}
    return {"label": "ENGINEERING FIXTURES — NOT MODEL PERFORMANCE" if any(r["fixture"] for r in selected) else "MODEL RUNS — SYNTHETIC INCIDENT SUITE",
            "excluded_fixtures": len(results) - len(selected), "groups": groups}


def paired_delta(results, include_fixtures=False, seed=42, samples=1000, profiles=("baseline", "grounded")):
    """Task-clustered paired bootstrap. Missing/cross-config pairs are explicit."""
    import random
    if samples < 1 or len(profiles) != 2 or profiles[0] == profiles[1]:
        raise ValueError("invalid bootstrap/profiles")
    rows = [r for r in results if (include_fixtures or not r["fixture"]) and r["profile"] in profiles]
    by_key = {}
    for r in rows:
        key = (r["task_id"], r["trial"], r["config_hash"])
        if r["profile"] in by_key.setdefault(key, {}):
            raise ValueError("duplicate trial")
        by_key[key][r["profile"]] = r
    deltas, missing = {}, []
    for key, pair in by_key.items():
        if all(p in pair for p in profiles):
            deltas.setdefault(key[0], []).append(int(pair[profiles[1]]["success"]) - int(pair[profiles[0]]["success"]))
        else:
            missing.append({"task_id": key[0], "trial": key[1], "config_hash": key[2], "missing_profiles": [p for p in profiles if p not in pair]})
    info = {"profiles": list(profiles), "paired_tasks": len(deltas), "paired_trials": sum(len(v) for v in deltas.values()), "missing_pair_trials": len(missing), "missing_pairs": missing}
    if not deltas:
        return {**info, "delta": None, "bootstrap95": None}
    means = [sum(values) / len(values) for values in deltas.values()]
    rng = random.Random(seed)
    boot = sorted(sum(rng.choice(means) for _ in means) / len(means) for _ in range(samples))
    return {**info, "delta": sum(means)/len(means), "bootstrap95": [boot[int(samples*.025)], boot[min(samples-1, int(samples*.975))]]}
