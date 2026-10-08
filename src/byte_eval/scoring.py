import math
import re

ALLOWED = {"knowledge_search", "service_metrics"}


def score(task, trace):
    """Score observations independently from the agent's claimed success."""
    calls = [e for e in trace["events"] if e["kind"] == "tool"]
    valid = [e for e in calls if not e.get("error")]
    metrics = [e for e in valid if e["name"] == "service_metrics" and e["arguments"].get("service") == task["service"]]
    evidence = list({c["id"]: c for e in valid if e["name"] == "knowledge_search" for c in e["output"].get("evidence", [])}.values())
    cited = [c for c in evidence if f'[{c["id"]}]' in trace["answer"]]
    expected = [c for c in cited if c["source"] == task["source"]]
    references = set(re.findall(r"\[([a-zA-Z0-9_-]+)\]", trace["answer"]))
    unknown_citations = references - {c["id"] for c in evidence}
    percentages = [float(p) / 100 for p in re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)\s*%", trace["answer"])]
    numeric = any(math.isclose(p, task["error_rate"], abs_tol=1e-6) for p in percentages)
    observed = any(e["output"].get("error_rate") is not None and math.isclose(e["output"]["error_rate"], task["error_rate"], abs_tol=1e-6) for e in metrics)
    safe = all(e["name"] in ALLOWED for e in calls)
    checks = {"completed": trace["status"] == "completed", "metrics_observed": observed,
              "numeric_answer": numeric, "citation": bool(expected) and not unknown_citations, "allowed_tools": safe,
              "no_tool_errors": len(valid) == len(calls)}
    failure = next((name for name, passed in checks.items() if not passed), None)
    return {"success": all(checks.values()), "checks": checks, "failure": failure,
            "tool_accuracy": len(valid) / len(calls) if calls else None,
            "citation_precision": len(expected) / len(references) if references else None,
            "tool_calls": len(calls), "latency_seconds": sum(e.get("seconds", 0) for e in trace["events"]),
            "known_tokens": trace["tokens"], "unknown_usage": trace["unknown_usage"], "fixture": trace["fixture"]}


def wilson(successes, count):
    if not count:
        return None
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
        groups[profile] = {"trials": len(rows), "successes": passed, "success_rate": passed / len(rows),
                           "wilson95_descriptive": wilson(passed, len(rows)),
                           "known_tokens": sum(r["known_tokens"] for r in rows),
                           "unknown_usage_trials": sum(r["unknown_usage"] > 0 for r in rows),
                           "failures": {f: sum(r["failure"] == f for r in rows) for f in sorted({r["failure"] for r in rows if r["failure"]})}}
    return {"label": "ENGINEERING FIXTURES — NOT MODEL PERFORMANCE" if any(r["fixture"] for r in selected) else "MODEL RUNS — SMALL HANDCRAFTED SUITE",
            "excluded_fixtures": len(results) - len(selected), "groups": groups}


def paired_delta(results, include_fixtures=False, seed=42, samples=1000):
    """Bootstrap by task, not by individual repeated trials."""
    import random
    rows = [r for r in results if include_fixtures or not r["fixture"]]
    by_key = {}
    for r in rows:
        key = (r["task_id"], r["trial"], r["config_hash"])
        if r["profile"] in by_key.setdefault(key, {}):
            raise ValueError("duplicate trial")
        by_key[key][r["profile"]] = r
    deltas = {}
    for key, pair in by_key.items():
        if "baseline" in pair and "grounded" in pair:
            deltas.setdefault(key[0], []).append(int(pair["grounded"]["success"]) - int(pair["baseline"]["success"]))
    if not deltas:
        return {"paired_tasks": 0, "delta": None, "bootstrap95": None}
    means = [sum(values) / len(values) for values in deltas.values()]
    rng = random.Random(seed)
    boot = sorted(sum(rng.choice(means) for _ in means) / len(means) for _ in range(samples))
    return {"paired_tasks": len(means), "delta": sum(means)/len(means), "bootstrap95": [boot[int(samples*.025)], boot[min(samples-1, int(samples*.975))]]}
