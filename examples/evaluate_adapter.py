"""Evaluate a saved constrained LM adapter without training or model downloads.

Install both projects plus optional training dependencies. Supply the pinned
local base snapshot, a published checkpoint folder, and an existing corpus.
"""
import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from byte_eval.training.environment import load_partition
from byte_eval.training.policy import LanguagePolicy, file_hash
from byte_eval.training.runner import evaluate, source_hashes, verify_download_receipt, write_json


def verify_checkpoint(checkpoint, model_id, revision, rank):
    checkpoint = Path(checkpoint)
    config = json.loads((checkpoint / "adapter_config.json").read_text(encoding="utf-8"))
    expected = {"base_model_name_or_path": model_id, "revision": revision,
                "r": rank, "lora_alpha": rank * 2, "bias": "none",
                "task_type": "CAUSAL_LM", "peft_type": "LORA", "lora_dropout": 0.0}
    for field, value in expected.items():
        if config.get(field) != value:
            raise ValueError("adapter configuration mismatch: " + field)
    if set(config.get("target_modules", [])) != {"q_proj", "v_proj"}:
        raise ValueError("adapter target modules must be exactly q_proj and v_proj")
    if config.get("use_dora", False) or config.get("use_rslora", False):
        raise ValueError("this consumer supports the original plain rank-4 LoRA configuration")
    weights = json.loads((checkpoint / "weights.json").read_text(encoding="utf-8"))
    files = {}
    for filename in ("adapter_model.safetensors", "adapter_config.json"):
        path = checkpoint / filename
        actual = {"sha256": file_hash(path), "bytes": path.stat().st_size}
        recorded = weights.get("files", {}).get(filename)
        if actual != recorded:
            raise ValueError("checkpoint file checksum/size mismatch: " + filename)
        files[filename] = actual
    parameter_sha = weights.get("parameter_sha256")
    if not isinstance(parameter_sha, str) or len(parameter_sha) != 64 or any(c not in "0123456789abcdef" for c in parameter_sha):
        raise ValueError("checkpoint requires a valid trainable parameter SHA-256")
    return {"configuration_matches": True, "file_checksums_match": True,
            "expected_parameter_sha256": parameter_sha, "files": files,
            "weights_metadata_sha256": file_hash(checkpoint / "weights.json")}


def compare_reference(actual, reference_path):
    """Compare deterministic task decisions, actions, and every oracle check.

    Timing and floating model probabilities are not claimed to match exactly.
    They remain in the actual saved traces for separate inspection.
    """
    reference_path = Path(reference_path)
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    selected_splits = {row["split"] for row in actual["results"]}
    expected_rows = [row for row in reference["results"] if row["split"] in selected_splits]
    order_matches = [row["task_id"] for row in expected_rows] == [row["task_id"] for row in actual["results"]]
    by_id = {row["task_id"]: row for row in expected_rows}
    if len(by_id) != len(expected_rows):
        raise ValueError("reference evaluation has duplicate task ids")
    rows = []
    for row in actual["results"]:
        expected = by_id.get(row["task_id"])
        checks = {"task_present": expected is not None,
                  "actions_match": expected is not None and row["actions"] == expected["actions"],
                  "parsed_decision_matches": expected is not None and row["score"]["parsed_answer"] == expected["score"]["parsed_answer"],
                  "success_matches": expected is not None and row["score"]["success"] == expected["score"]["success"],
                  "decision_accuracy_matches": expected is not None and row["score"]["decision_correct"] == expected["score"]["decision_correct"],
                  "all_oracle_checks_match": expected is not None and row["score"]["checks"] == expected["score"]["checks"],
                  "terminal_status_matches": expected is not None and row["trace"]["status"] == expected["trace"]["status"]}
        rows.append({"task_id": row["task_id"], "checks": checks, "matches": all(checks.values())})
    return {"reference_sha256": file_hash(reference_path), "reference_stage": reference.get("stage"),
            "task_order_matches": order_matches, "tasks": rows,
            "complete_match": order_matches and bool(rows) and all(row["matches"] for row in rows),
            "comparison": "task order, discrete actions, parsed decisions, success and all oracle checks; timing/probabilities excluded"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="local pinned base model snapshot; no automatic download")
    parser.add_argument("--revision", required=True, help="full immutable Hugging Face revision SHA")
    parser.add_argument("--model-id", default="HuggingFaceTB/SmolLM2-135M-Instruct")
    parser.add_argument("--checkpoint", required=True, help="initial, sft, or reinforce folder containing adapter/config/weights.json")
    parser.add_argument("--dataset", required=True, help="existing platform services.json with its knowledge and metrics.sqlite")
    parser.add_argument("--output", required=True, help="new output directory")
    parser.add_argument("--split", choices=("validation", "holdout", "all"), default="all")
    parser.add_argument("--reference", help="optional original stage-evaluation.json for deterministic decision/trace reproduction checks")
    parser.add_argument("--max-length", type=int, default=384)
    parser.add_argument("--rank", type=int, choices=(4,), default=4)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        parser.error("output must be a new directory")
    checkpoint = Path(args.checkpoint)
    checks = verify_checkpoint(checkpoint, args.model_id, args.revision, args.rank)
    _, validation, holdout, partition = load_partition(args.dataset)
    tasks = validation if args.split == "validation" else holdout if args.split == "holdout" else validation + holdout
    provenance = verify_download_receipt(args.model, args.model_id, args.revision)
    # Imports below are optional and happen only for an actual evaluation.
    from peft import set_peft_model_state_dict
    from safetensors.torch import load_file
    from byte_agent.knowledge import Knowledge
    from byte_agent.tools import registry
    policy = LanguagePolicy(args.model, args.revision, args.seed, args.threads, args.max_length, args.rank, args.model_id)
    state = load_file(str(checkpoint / "adapter_model.safetensors"))
    # reload_adapter verifies the adapter just saved in memory. Consumer loading
    # a different stage instead imports that file into the active adapter.
    set_peft_model_state_dict(policy.model, state, adapter_name="default")
    loaded_sha = policy.parameter_hash()
    if loaded_sha != checks["expected_parameter_sha256"]:
        raise ValueError("loaded adapter parameter hash differs from published weights metadata")
    checks.update(loaded_parameter_sha256=loaded_sha, loaded_parameter_hash_matches=True)
    stage = {"initial": "base", "sft": "sft", "reinforce": "reinforce"}.get(checkpoint.name, "adapter")
    output.mkdir(parents=True)
    manifest = {"schema_version": 1, "kind": "saved adapter consumer, evaluation only", "started_at": datetime.now(timezone.utc).isoformat(),
                "model_id": args.model_id, "model_revision": args.revision, "base_model_provenance": provenance,
                "checkpoint_stage": stage, "checkpoint_checks": checks, "partition": partition,
                "config": {"split": args.split, "task_ids": [task["id"] for task in tasks],
                           "max_length": args.max_length, "rank": args.rank, "threads": args.threads, "seed": args.seed,
                           "decoder": "greedy", "optimizer_steps": 0, "max_episode_actions": 4},
                "source_hashes": source_hashes(), "consumer_script_sha256": file_hash(Path(__file__)),
                "python": platform.python_version()}
    write_json(output / "manifest.json", manifest)
    knowledge = Knowledge(output / "knowledge.sqlite")
    try:
        knowledge.ingest(Path(args.dataset).parent / "knowledge")
        tools = registry(knowledge, Path(args.dataset).parent / "metrics.sqlite")
        result = evaluate(policy, tasks, tools, output, stage)
        unchanged = policy.parameter_hash() == loaded_sha
        reference = compare_reference(result, args.reference) if args.reference else None
        summary = {"complete": unchanged and (reference is None or reference["complete_match"]),
                   "evaluation_only": True, "optimizer_steps": 0, "parameter_hash_unchanged": unchanged,
                   "checkpoint_checks": checks, "groups": result["groups"], "reference_comparison": reference}
        write_json(output / "summary.json", summary)
        report = "# Saved adapter consumer evaluation\n\n"
        report += "Loads the pinned base and published LoRA tensors, verifies actual file and parameter hashes, and executes the same constrained policy with actual read-only tools. No training/optimizer steps or model downloads occur.\n\n"
        report += "| Split | Episodes | Full contract successes with renderer | All three tools observed |\n|---|---:|---:|---:|\n"
        for split, group in result["groups"].items():
            report += f'| {split} | {group["episodes"]} | {group["full_contract_successes_with_renderer"]} | {group["all_three_tools_observed"]} |\n'
        report += "\nParameter hash unchanged: `" + str(unchanged).lower() + "`."
        if reference:
            report += " Original task order/actions/decisions/all oracle checks reproduce: `" + str(reference["complete_match"]).lower() + "`. Timing and floating probabilities are not asserted equal."
        (output / "report.md").write_text(report + "\n", encoding="utf-8")
    except Exception as exc:
        write_json(output / "interrupted.json", {"complete": False, "type": type(exc).__name__})
        raise
    finally:
        knowledge.db.close()
    print(json.dumps({"complete": summary["complete"], "episodes": len(tasks), "loaded_parameter_hash_matches": True,
                      "parameter_hash_unchanged": unchanged, "reference_match": reference["complete_match"] if reference else None}), flush=True)
    return 0 if summary["complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
