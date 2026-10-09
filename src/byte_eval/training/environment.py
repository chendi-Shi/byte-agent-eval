"""Multi-step, read-only tool episodes for a constrained LM action vocabulary."""
import hashlib
import json
import re
import time
from pathlib import Path

from byte_eval.scoring import score

ACTION_CODES = tuple("ABCDEFGHI")
TOOL_ACTIONS = {"A": "service_metrics", "B": "knowledge_search", "C": "incident_changes"}
DECISIONS = {
    "D": ("incident", "release_regression", "rollback_review", "causality_unproven"),
    "E": ("incident", "dependency_outage", "dependency_escalation", "causality_unproven"),
    "F": ("incident", "capacity_pressure", "capacity_review", "causality_unproven"),
    "G": ("healthy", "none", "monitor", "none_detected"),
    "H": ("insufficient_data", "insufficient_evidence", "collect_evidence", "insufficient_data"),
    "I": ("incident", "conflicting_evidence", "verify_changes", "conflicting_evidence"),
}
VALIDATION_IDS = ("social-notify", "ads-auction", "commerce-checkout", "live-gifts", "message-presence", "video-playback")
LEGEND = (
    "Read-only incident diagnosis. Choose ONE action letter. "
    "A=read metrics; B=read policy; C=read changes; "
    "D=release incident; E=dependency incident; F=capacity incident; "
    "G=healthy; H=missing evidence; I=conflicting incident. "
    "Inspect A,B,C before diagnosis. Use current evidence only.\n"
)


def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def load_partition(dataset):
    """Freeze an explicit 18/6 development partition and a public 8-case test set."""
    path = Path(dataset)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    tasks = manifest["tasks"]
    ids = [task["id"] for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate task ids")
    development = [task for task in tasks if task["split"] == "dev"]
    unknown = set(VALIDATION_IDS) - {task["id"] for task in development}
    if unknown:
        raise ValueError("validation tasks absent from development split")
    train = [task for task in development if task["id"] not in VALIDATION_IDS]
    validation = [task for task in development if task["id"] in VALIDATION_IDS]
    held = [task for task in tasks if task["split"] == "holdout"]
    if len(train) != 18 or len(validation) != 6 or len(held) != 8:
        raise ValueError("expected documented 18/6 development and 8 public holdout tasks")
    info = {"schema_version": 1, "task_manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "training_ids": [t["id"] for t in train], "validation_ids": [t["id"] for t in validation],
            "public_holdout_ids": [t["id"] for t in held], "source_synthetic": manifest.get("synthetic", False),
            "training_label": "synthetic-supervised tool-action demonstrations, not model-generated agent trajectories",
            "heldout_use": "evaluation only; public suite is not an unseen benchmark"}
    info["partition_hash"] = json_hash(info)
    return train, validation, held, info


def teacher_decision(task):
    if task["split"] != "dev":
        raise ValueError("holdout must never become a training demonstration")
    target = (task["status"], task["likely_cause"], task["recommendation"], task["expected_uncertainty"])
    return next(code for code, decision in DECISIONS.items() if decision == target)


class ToolEpisode:
    """The LM chooses actions; the host binds service/SQL/schema/rendering.

    Gold fields are used only by finish()'s independent reward/scoring, never
    by prompt(). Tool output text is summarized mechanically, not diagnosed.
    """
    def __init__(self, task, tools, max_steps=4):
        if not 1 <= max_steps <= 12:
            raise ValueError("invalid episode budget")
        self.task, self.tools, self.max_steps = task, tools, max_steps
        self.events, self.actions, self.outputs = [], [], {}
        self.done, self.answer, self.tokens = False, None, 0
        self.started = time.perf_counter()

    def prompt(self):
        lines = [LEGEND, "Service=" + self.task["service"] + ". Actions=" + "".join(self.actions)]
        metrics = self.outputs.get("service_metrics")
        if metrics is not None:
            keys = ("samples", "error_rate", "recent_error_rate", "baseline_error_rate", "recent_max_p95_ms", "baseline_requests", "recent_requests")
            lines.append("Metrics=" + json.dumps({k: metrics.get(k) for k in keys}, separators=(",", ":")))
        policy = self.outputs.get("knowledge_search")
        if policy is not None:
            text = "\n".join(item.get("text", "") for item in policy.get("evidence", []))
            error = re.search(r"recent_error_rate\s*>=\s*([0-9.]+)", text)
            latency = re.search(r"recent_max_p95_ms\s*>\s*([0-9]+)", text)
            lines.append("Policy=" + json.dumps({"found": bool(policy.get("evidence")),
                         "error_limit": float(error[1]) if error else None,
                         "latency_limit": int(latency[1]) if latency else None}, separators=(",", ":")))
        changes = self.outputs.get("incident_changes")
        if changes is not None:
            # Kind/status/minute are actual database observations, not a derived diagnosis.
            lines.append("Changes=" + json.dumps([{k: item.get(k) for k in ("kind", "status", "minute")} for item in changes.get("changes", [])], separators=(",", ":")))
        lines.append("Next action:")
        return "\n".join(lines)

    def step(self, code):
        if self.done:
            raise ValueError("episode already finished")
        if code not in ACTION_CODES:
            raise ValueError("unknown action")
        self.actions.append(code)
        if code in TOOL_ACTIONS:
            name = TOOL_ACTIONS[code]
            arguments = {"service": self.task["service"]}
            if name == "service_metrics":
                arguments["window_minutes"] = 30
            elif name == "knowledge_search":
                arguments.update(query="incident policy observation window status diagnostic evidence uncertainty " + self.task["service"], limit=5)
            started = time.perf_counter()
            event = {"kind": "tool", "name": name, "arguments": arguments}
            try:
                event["output"] = self.tools[name].call(arguments)
                self.outputs[name] = event["output"]
            except (ValueError, OSError) as exc:
                event["error"] = str(exc)
            event["seconds"] = time.perf_counter() - started
            self.events.append(event)
        else:
            status, cause, recommendation, uncertainty = DECISIONS[code]
            citations = []
            for name in ("knowledge_search", "incident_changes"):
                for item in self.outputs.get(name, {}).get("evidence", []):
                    if item.get("id") and item["id"] not in citations:
                        citations.append(item["id"])
            # Mechanical rendering cannot pick a diagnosis: the LM's token did that.
            self.answer = json.dumps({"service": self.task["service"],
                "error_rate": self.outputs.get("service_metrics", {}).get("error_rate"),
                "status": status, "likely_cause": cause, "recommendation": recommendation,
                "uncertainty": uncertainty, "citations": citations})
            self.done = True
        if len(self.actions) >= self.max_steps:
            self.done = True
        return self.done

    def finish(self):
        trace = {"status": "completed" if self.answer is not None else "budget_exceeded", "answer": self.answer or "",
                 "events": self.events, "tokens": self.tokens, "unknown_usage": 0, "fixture": False}
        result = score(self.task, trace)
        unique_tools = {e["name"] for e in self.events if "output" in e and not e.get("error")}
        repeats = len(self.events) - len(unique_tools)
        # Reward derives from executed tools and independent terminal scoring.
        # It is never the teacher label lookup and doesn't grant evidence for an uncalled tool.
        reward = 0.1 * len(unique_tools) - 0.1 * repeats
        reward += 1.0 if result["success"] else (0.2 if result["decision_correct"] else 0.0)
        if not result["checks"]["required_tools"]:
            reward -= 0.3
        if self.answer is None:
            reward -= 0.2
        return {"task_id": self.task["id"], "split": self.task["split"], "actions": self.actions,
                "reward": round(reward, 6), "score": result, "trace": trace,
                "wall_seconds": time.perf_counter() - self.started}


def demonstrations(train_tasks, tools):
    rows = []
    for task in train_tasks:
        if task["split"] != "dev" or task["id"] in VALIDATION_IDS:
            raise ValueError("training may only use the frozen training development ids")
        episode = ToolEpisode(task, tools)
        for code in ("A", "B", "C", teacher_decision(task)):
            rows.append({"task_id": task["id"], "split": "dev", "prompt": episode.prompt(), "action": code,
                         "provenance": "synthetic-supervised; teacher uses development oracle; observations use actual tools"})
            episode.step(code)
    return rows
