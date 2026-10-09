"""Technical checks for candidate traces, explicitly not human review."""
import hashlib
import json
from pathlib import Path

from byte_eval.scoring import score


def review_candidates(experiment_paths):
    reports = []
    for directory in map(Path, experiment_paths):
        manifest = json.loads((directory / "experiment.json").read_text(encoding="utf-8"))
        tasks = {task["id"]: task for task in manifest["tasks"]}
        results = json.loads((directory / "results.json").read_text(encoding="utf-8"))
        rows = [json.loads(line) for line in (directory / "sft-candidates.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in rows:
            metadata = row["metadata"]
            source_sha = metadata["source_trace_sha256"]
            matched = [result for result in results if result["task_id"] == metadata["task_id"] and result["trace_sha256"] == source_sha]
            if len(matched) != 1:
                raise ValueError("candidate trace must map to exactly one scored result")
            result = matched[0]
            relative = Path(result["trace_path"])
            trace_path = (directory / relative).resolve()
            if relative.is_absolute() or not trace_path.is_relative_to(directory.resolve()):
                raise ValueError("candidate path escapes experiment")
            body = trace_path.read_bytes()
            trace = json.loads(body)
            task = tasks[result["task_id"]]
            rescored = score(task, trace, result["available_tools"])
            checks = {"development_only": task["split"] == "dev" and result["split"] == "dev",
                      "not_fixture": not trace["fixture"] and not result["fixture"],
                      "complete_trace": trace["status"] == "completed",
                      "trace_checksum": hashlib.sha256(body).hexdigest() == source_sha,
                      "messages_unchanged": row["messages"] == trace["messages"],
                      "config_match": metadata["config_hash"] == result["config_hash"] == manifest["config_hash"],
                      "independent_rescore": rescored["success"],
                      "human_review_marker_preserved": metadata.get("human_review_required") is True}
            reports.append({"task_id": task["id"], "source_trace_sha256": source_sha,
                            "checks": checks, "technical_checks_passed": all(checks.values()),
                            "human_review_required": True, "included_in_tiny_policy_training": False,
                            "review_kind": "automated mechanical provenance and independent oracle audit"})
    return {"candidates": reports, "technical_passes": sum(row["technical_checks_passed"] for row in reports),
            "count": len(reports), "human_review_complete": False,
            "training_use": "None: new 18-task synthetic-supervised demonstrations are separately identified."}
