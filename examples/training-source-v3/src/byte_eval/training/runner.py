"""Reproducible optional SFT and REINFORCE experiment for a small causal LM."""
import argparse
import importlib.metadata
import json
import platform
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from byte_eval.scoring import wilson
from .environment import ToolEpisode, demonstrations, json_hash, load_partition
from .policy import LanguagePolicy, file_hash
from .review import review_candidates


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def source_hashes():
    import byte_agent
    import byte_eval
    hashes = {}
    for name, package in (("platform", byte_agent), ("eval", byte_eval)):
        directory = Path(package.__file__).parent
        for path in sorted(directory.rglob("*.py")):
            hashes[name + "/" + path.relative_to(directory).as_posix()] = file_hash(path)
    return hashes


def verify_download_receipt(directory, model_id, revision):
    """Verify a local pinned-download receipt without claiming a hub signature."""
    directory = Path(directory).resolve()
    receipt_path = directory / "download-manifest.json"
    if not receipt_path.exists():
        return {"status": "operator-declared provenance; no download receipt", "repository": model_id, "revision": revision}
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("repository") != model_id or receipt.get("revision") != revision:
        raise ValueError("download receipt repository/revision mismatch")
    files = receipt.get("files", {})
    if "model.safetensors" not in files:
        raise ValueError("download receipt lacks model.safetensors")
    for filename, metadata in files.items():
        path = (directory / filename).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise ValueError("download receipt file is missing or escapes the snapshot")
        if file_hash(path) != metadata.get("sha256") or path.stat().st_size != metadata.get("bytes"):
            raise ValueError("download receipt file checksum/size mismatch: " + filename)
    return {"status": "local pinned-download receipt verified; not a publisher signature",
            "repository": model_id, "revision": revision, "source": receipt.get("source"),
            "receipt_sha256": file_hash(receipt_path), "verified_files": len(files),
            "model_safetensors_sha256": files["model.safetensors"]["sha256"]}


def run_episode(policy, task, tools, sample=False):
    episode = ToolEpisode(task, tools)
    states = []
    while not episode.done:
        prompt = episode.prompt()
        action, tokens, probabilities, context = policy.act(prompt, sample=sample)
        states.append({"prompt": prompt, "action": action, "input_tokens": tokens, "probabilities": probabilities, "context": context})
        episode.tokens += tokens + 1
        episode.step(action)
    return {"states": states, "episode": episode.finish()}


def evaluate(policy, tasks, tools, output, stage):
    rows = []
    for task in tasks:
        rollout = run_episode(policy, task, tools)
        row = rollout["episode"]
        row["decoder"] = "greedy one-of-nine original LM vocabulary tokens"
        row["stage"] = stage
        trace_path = Path("traces") / stage / (task["id"] + ".json")
        write_json(output / trace_path, rollout)
        row["trace_path"] = trace_path.as_posix()
        row["trace_sha256"] = file_hash(output / trace_path)
        rows.append(row)
    groups = {}
    for split in sorted({row["split"] for row in rows}):
        selected = [row for row in rows if row["split"] == split]
        passed = sum(row["score"]["success"] for row in selected)
        groups[split] = {"episodes": len(selected), "full_contract_successes_with_renderer": passed,
            "full_contract_success_rate_with_renderer": passed / len(selected),
            "decision_correct": sum(row["score"]["decision_correct"] for row in selected),
            "all_three_tools_observed": sum(row["score"]["checks"]["required_tools"] for row in selected),
            "mean_reward": sum(row["reward"] for row in selected) / len(selected),
            "wilson95_descriptive": wilson(passed, len(selected)),
            "interpretation": "constrained decoder plus mechanical numeric/citation/schema renderer; not free-form Qwen task performance"}
    result = {"stage": stage, "groups": groups, "results": rows}
    write_json(output / (stage + "-evaluation.json"), result)
    return result


def execute(args):
    from byte_agent.knowledge import Knowledge
    from byte_agent.tools import registry
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / "manifest.json").exists():
        raise ValueError("output already contains a training experiment; choose a new directory")
    train, validation, held, partition = load_partition(args.dataset)
    knowledge = Knowledge(output / "knowledge.sqlite")
    knowledge.ingest(Path(args.dataset).parent / "knowledge")
    tools = registry(knowledge, Path(args.dataset).parent / "metrics.sqlite")
    training_rows = demonstrations(train, tools)
    write_json(output / "partition.json", partition)
    (output / "demonstrations.jsonl").write_text("".join(json.dumps(row) + "\n" for row in training_rows), encoding="utf-8")
    review = review_candidates(args.review_experiment) if args.review_experiment else {"count": 0, "human_review_complete": False}
    write_json(output / "candidate-review.json", review)
    model_path = Path(args.model)
    model_files = {path.name: {"sha256": file_hash(path), "bytes": path.stat().st_size}
                   for path in sorted(model_path.iterdir()) if path.is_file() and path.suffix in (".safetensors", ".json")}
    provenance = verify_download_receipt(model_path, args.model_id, args.revision)
    dependencies = {}
    for dependency in ("torch", "transformers", "peft", "accelerate", "safetensors", "huggingface-hub"):
        dependencies[dependency] = importlib.metadata.version(dependency)
    manifest = {"schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(),
        "model_id": args.model_id, "model_revision": args.revision, "base_model_files": model_files,
        "base_model_provenance": provenance,
        "algorithm": {"sft": "conditional cross entropy on nine existing LM vocabulary tokens",
                      "rl": "on-policy REINFORCE with leave-one-out group reward baseline and entropy bonus",
                      "reward": "0.1 per distinct successful tool, -0.1 repeated tool, +1 full contract success else +0.2 decision correct; -0.3 missing tools, -0.2 no final decision"},
        "partition": partition, "demonstration_rows": len(training_rows),
        "demonstration_sha256": file_hash(output / "demonstrations.jsonl"), "candidate_review_count": review["count"],
        "config": {"seed": args.seed, "threads": args.threads, "max_length": args.max_length,
                   "rank": args.rank, "sft_steps": args.sft_steps, "sft_batch": args.batch_size,
                   "sft_learning_rate": args.sft_lr, "rl_steps": args.rl_steps, "rl_group": args.rl_group,
                   "rl_learning_rate": args.rl_lr, "entropy_weight": args.entropy_weight},
        "runtime": {"python": platform.python_version(), "system": platform.system(), "dependencies": dependencies},
        "source_hashes": source_hashes(), "benchmark_only": args.benchmark_only,
        "limitations": ["English 135M constrained tool policy, not the 4B Qwen system", "public synthetic test set", "fixed operator service/arguments, host-rendered numeric values/citations/schema", "no human review claim", "single CPU machine"]}
    manifest["config_hash"] = json_hash(manifest)
    write_json(output / "manifest.json", manifest)
    policy = LanguagePolicy(args.model, args.revision, args.seed, args.threads, args.max_length, args.rank, args.model_id)
    before = policy.parameter_hash()
    initial = policy.save(output / "checkpoints" / "initial")
    write_json(output / "checkpoints" / "initial" / "weights.json", initial)
    # Freeze data and model/config before observing any evaluation outcomes.
    eval_tasks = validation + held
    stages = {} if args.benchmark_only else {"base": evaluate(policy, eval_tasks, tools, output, "base")}
    rng = random.Random(args.seed)
    train_order = list(range(len(training_rows)))
    rng.shuffle(train_order)
    training_log = []
    run_started = time.perf_counter()
    for step in range(args.sft_steps):
        if step and step * args.batch_size % len(train_order) == 0:
            rng.shuffle(train_order)
        batch = [training_rows[train_order[(step * args.batch_size + offset) % len(train_order)]] for offset in range(args.batch_size)]
        started = time.perf_counter()
        details = policy.supervised_step(batch, args.sft_lr)
        training_log.append({"phase": "sft", "step": step + 1, "seconds": time.perf_counter()-started,
                             "task_ids": [row["task_id"] for row in batch], **details})
        write_json(output / "training-log.json", training_log)
        print(json.dumps({"phase": "sft", "step": step+1, "loss": details["loss"], "seconds": training_log[-1]["seconds"]}), flush=True)
    sft = policy.save(output / "checkpoints" / "sft")
    sft_reload = policy.reload_adapter(output / "checkpoints" / "sft")
    sft["reload_parameter_sha256"] = sft_reload
    sft["reload_exact"] = sft_reload == sft["parameter_sha256"]
    sft["changed_from_initial"] = before != sft["parameter_sha256"]
    write_json(output / "checkpoints" / "sft" / "weights.json", sft)
    if not args.benchmark_only:
        stages["sft"] = evaluate(policy, eval_tasks, tools, output, "sft")
    policy.begin_reinforce(args.rl_lr)
    active_rl_steps = 0
    for step in range(args.rl_steps if not args.benchmark_only else 0):
        task = train[step % len(train)]
        started = time.perf_counter()
        rollouts = [run_episode(policy, task, tools, sample=True) for _ in range(args.rl_group)]
        write_json(output / "rl-rollouts" / (str(step+1) + ".json"), rollouts)
        details = policy.reinforce_step(rollouts, args.rl_lr, args.entropy_weight, args.batch_size)
        active_rl_steps += int(details["reward_gradient_active"] and details["parameters_changed"])
        training_log.append({"phase": "reinforce", "step": step+1, "task_id": task["id"],
                             "seconds": time.perf_counter()-started, **details})
        write_json(output / "training-log.json", training_log)
        print(json.dumps({"phase": "reinforce", "step": step+1, "rewards": details["rewards"], "seconds": training_log[-1]["seconds"]}), flush=True)
    final = policy.save(output / "checkpoints" / "reinforce")
    final["reload_parameter_sha256"] = policy.reload_adapter(output / "checkpoints" / "reinforce")
    final["reload_exact"] = final["reload_parameter_sha256"] == final["parameter_sha256"]
    final["changed_from_sft"] = final["parameter_sha256"] != sft["parameter_sha256"]
    final["reward_gradient_active_steps"] = active_rl_steps
    write_json(output / "checkpoints" / "reinforce" / "weights.json", final)
    if not args.benchmark_only:
        stages["reinforce"] = evaluate(policy, eval_tasks, tools, output, "reinforce")
    checks = {"sft_weights_changed": sft["changed_from_initial"], "sft_reload_exact": sft["reload_exact"],
              "rl_weights_changed": final["changed_from_sft"], "rl_reward_gradient_active": active_rl_steps > 0,
              "rl_reload_exact": final["reload_exact"]}
    required_checks = {key: value for key, value in checks.items() if not args.benchmark_only or key.startswith("sft")}
    summary = {"complete": all(required_checks.values()), "benchmark_only": args.benchmark_only, "checks": checks,
               "seconds_excluding_model_load_and_base_evaluation": time.perf_counter()-run_started,
               "checkpoints": {"initial": initial, "sft": sft, "reinforce": final},
               "evaluations": {stage: evaluation["groups"] for stage, evaluation in stages.items()},
               "config_hash": manifest["config_hash"], "claim": "actual pretrained LM LoRA parameter updates, bounded synthetic tool-policy experiment"}
    write_json(output / "summary.json", summary)
    report = "# Actual small language-model tool-policy training\n\n"
    report += "This experiment updates SmolLM2 LoRA attention weights through supervised token loss and executed-tool REINFORCE rewards. Its constrained actions and mechanical renderer differ from the free-form Qwen benchmark.\n\n"
    report += "| Stage | Split | Episodes | Full contract successes with renderer | All three tools observed | Mean reward |\n|---|---|---:|---:|---:|---:|\n"
    for stage, evaluation in stages.items():
        for split, group in evaluation["groups"].items():
            report += f'| {stage} | {split} | {group["episodes"]} | {group["full_contract_successes_with_renderer"]} | {group["all_three_tools_observed"]} | {group["mean_reward"]:.3f} |\n'
    report += "\nWeight/reload checks: `" + json.dumps(checks) + "`. No improvement is assumed. All evaluation failures and RL sampled actions/rewards remain in the trace files. The public eight-task test set is evaluation only; this is not an unseen production result.\n"
    (output / "report.md").write_text(report, encoding="utf-8")
    knowledge.db.close()
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="local pinned Hugging Face snapshot directory")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--model-id", default="HuggingFaceTB/SmolLM2-135M-Instruct")
    parser.add_argument("--dataset", required=True, help="services.json from the platform dataset generator")
    parser.add_argument("--output", required=True)
    parser.add_argument("--review-experiment", action="append", default=[])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=384)
    parser.add_argument("--rank", type=int, default=4)
    parser.add_argument("--sft-steps", type=int, default=24)
    parser.add_argument("--rl-steps", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--rl-group", type=int, default=4)
    parser.add_argument("--sft-lr", type=float, default=0.001)
    parser.add_argument("--rl-lr", type=float, default=0.0001)
    parser.add_argument("--entropy-weight", type=float, default=0.0)
    parser.add_argument("--benchmark-only", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.sft_steps <= 10000 or not 0 <= args.rl_steps <= 10000 or not 1 <= args.batch_size <= 8 or not 2 <= args.rl_group <= 8:
        parser.error("invalid bounded training steps/batches/group")
    if not 0 < args.sft_lr <= 0.01 or not 0 < args.rl_lr <= 0.01 or not 0 <= args.entropy_weight <= 0.1:
        parser.error("invalid learning rates/entropy")
    try:
        result = execute(args)
    except Exception as exc:
        output = Path(args.output)
        if (output / "manifest.json").exists():
            write_json(output / "interrupted.json", {"type": type(exc).__name__, "message": str(exc), "complete": False})
        raise
    print(json.dumps({"complete": result["complete"], "checks": result["checks"]}), flush=True)
    return 0 if result["complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
