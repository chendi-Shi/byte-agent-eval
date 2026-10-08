import hashlib
import json
import sys
from pathlib import Path
from .scoring import score, summarize, paired_delta


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def run_suite(tasks_path, platform_path, output, fixture=False, model=None, base_url="http://127.0.0.1:11434", trials=1, split="dev"):
    if trials < 1:
        raise ValueError("trials must be positive")
    platform_path = Path(platform_path).resolve()
    if not (platform_path / "src/byte_agent/runtime.py").exists():
        raise ValueError("platform path must point to byte-agent-platform")
    # Import sibling package only from a deliberate user-selected project directory.
    sys.path.insert(0, str(platform_path / "src"))
    from byte_agent.knowledge import Knowledge
    from byte_agent.tools import registry
    from byte_agent.cli import seed_metrics
    from byte_agent.runtime import Runtime, SYSTEM
    from byte_agent.model import Scripted, Ollama
    tasks = json.loads(Path(tasks_path).read_text(encoding="utf-8"))
    tasks = [t for t in tasks if t["split"] == split]
    if not tasks or len({t["id"] for t in tasks}) != len(tasks):
        raise ValueError("empty suite or duplicate task ids")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    code = {p.relative_to(platform_path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((platform_path / "src").rglob("*.py"))}
    knowledge_files = {p.relative_to(platform_path).as_posix(): p.read_text(encoding="utf-8") for p in sorted((platform_path / "examples/knowledge").rglob("*.md"))}
    eval_code = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))}
    model_revision = None if fixture else Ollama(model, base_url).describe()
    metadata = {"schema": 1, "tasks": tasks, "platform_source": code, "eval_source": eval_code, "knowledge": knowledge_files,
                "model_revision": model_revision,
                "model": model, "endpoint": base_url, "fixture": fixture, "trials": trials, "split": split,
                "budgets": {"steps": 8, "calls": 16, "tokens": 12000}, "system": SYSTEM,
                "profiles": {"baseline": "You are an engineering assistant. Use tools to answer the task.", "grounded": SYSTEM}}
    config_hash = digest(metadata)
    manifest = output / "experiment.json"
    if manifest.exists() and json.loads(manifest.read_text(encoding="utf-8"))["config_hash"] != config_hash:
        raise ValueError("experiment configuration changed; choose a new output directory")
    manifest.write_text(json.dumps({**metadata, "config_hash": config_hash}, ensure_ascii=False, indent=2), encoding="utf-8")
    kb = Knowledge(output / "knowledge.sqlite")
    try:
        kb.ingest(platform_path / "examples/knowledge")
        metrics = output / "metrics.sqlite"
        seed_metrics(metrics)
        all_tools = registry(kb, metrics)
        results = []
        def save_results():
            (output / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        for task in tasks:
            for trial in range(trials):
                for profile in ("baseline", "grounded"):
                    tools = all_tools
                    if fixture:
                        evidence = kb.search(task["query"], 5)
                        citation = next((c["id"] for c in evidence if c["source"] == task["source"]), "missing")
                        calls = [{"name": "service_metrics", "arguments": {"service": task["service"]}}]
                        if profile == "grounded":
                            calls.append({"name": "knowledge_search", "arguments": {"query": task["query"]}})
                        agent = Scripted([{"calls": calls}, {"answer": f'Synthetic error rate: {task["error_rate"]*100:g}%. ' + (f'Runbook [{citation}].' if profile == "grounded" else "No runbook available.")}])
                    else:
                        if not model:
                            raise ValueError("model required outside fixture mode")
                        agent = Ollama(model, base_url)
                        agent.revision = model_revision
                    directory = output / task["id"] / str(trial) / profile
                    trace = Runtime(directory, agent, tools, system_prompt=metadata["profiles"][profile]).run(task["prompt"])
                    result = {**score(task, trace), "task_id": task["id"], "split": split, "trial": trial,
                              "profile": profile, "config_hash": config_hash, "trace_path": str((directory / "trace.json").resolve())}
                    results.append(result)
                    save_results()
                    if trace["status"] == "uncertain":
                        (output / "interrupted.json").write_text(json.dumps({"reason": "provider_uncertain", "task_id": task["id"], "profile": profile, "completed_trials": len(results), "planned_trials": len(tasks) * trials * 2}), encoding="utf-8")
                        return results
        save_results()
        return results
    finally:
        kb.db.close()


def report(output, include_fixtures=False):
    output = Path(output)
    results = json.loads((output / "results.json").read_text(encoding="utf-8"))
    summary = summarize(results, include_fixtures)
    summary["paired"] = paired_delta(results, include_fixtures)
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    text = "# Agent evaluation\n\n" + summary["label"] + "\n\n"
    text += "| Profile | Trials | Successes | Success rate | Unknown usage trials |\n|---|---:|---:|---:|---:|\n"
    for name, group in summary["groups"].items():
        text += f'| {name} | {group["trials"]} | {group["successes"]} | {group["success_rate"]:.1%} | {group["unknown_usage_trials"]} |\n'
    text += f'\nExcluded fixture trials: {summary["excluded_fixtures"]}.\n\n'
    if (output / "interrupted.json").exists():
        interruption = json.loads((output / "interrupted.json").read_text(encoding="utf-8"))
        summary["interrupted"] = interruption
        text += "INCOMPLETE EXPERIMENT: " + json.dumps(interruption) + "\n\n"
    text += "Task-clustered bootstrap: " + json.dumps(summary["paired"]) + "\n\n"
    text += "Handcrafted synthetic tasks; confidence intervals describe this suite only. Repeated tasks are not independent. Fixture profiles are scripted, so any difference is a pipeline check, not a model improvement.\n"
    (output / "report.md").write_text(text, encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def export_sft(output, destination):
    output = Path(output)
    manifest = json.loads((output / "experiment.json").read_text(encoding="utf-8"))
    tasks = {t["id"]: t for t in manifest["tasks"]}
    results = json.loads((output / "results.json").read_text(encoding="utf-8"))
    rows = []
    for result in results:
        if result["fixture"] or not result["success"] or result["split"] != "dev":
            continue
        path = Path(result["trace_path"]).resolve()
        if not path.is_relative_to(output.resolve()) or result["config_hash"] != manifest["config_hash"]:
            raise ValueError("trace path/configuration mismatch")
        trace = json.loads(path.read_text(encoding="utf-8"))
        if trace["fixture"] or trace["status"] != "completed":
            raise ValueError("result/trace mismatch")
        task = tasks[result["task_id"]]
        if task["split"] != "dev" or task["prompt"] != trace["task"] or not score(task, trace)["success"]:
            raise ValueError("trace failed independent re-validation")
        rows.append({"messages": trace["messages"], "metadata": {"task_id": result["task_id"], "config_hash": result["config_hash"], "format": "ollama-chat", "human_review_required": True}})
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return {"exported": len(rows), "format": "ollama-chat", "human_review_required": True, "excluded": "fixtures, failed runs, holdout"}
