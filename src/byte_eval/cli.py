import argparse
import json
from pathlib import Path
from .experiment import run_suite, report, export_sft


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run", "report", "export-sft"])
    parser.add_argument("--platform", type=Path, default=Path("../byte-agent-platform"))
    parser.add_argument("--tasks", type=Path, default=Path("benchmarks/tasks.json"))
    parser.add_argument("--output", type=Path, default=Path("runs/smoke"))
    parser.add_argument("--destination", type=Path, default=Path("runs/sft.jsonl"))
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--include-fixtures", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--split", choices=["dev", "holdout"], default="dev")
    parser.add_argument("--profiles", nargs="+", choices=["baseline", "grounded", "no-changes"], default=["baseline", "grounded", "no-changes"])
    parser.add_argument("--task-ids", nargs="+")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model-context", type=int, default=4096)
    parser.add_argument("--model-output", type=int, default=384)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--max-calls", type=int, default=16)
    parser.add_argument("--max-tokens", type=int, default=12000)
    args = parser.parse_args()
    if args.command == "run":
        if not args.fixture and not args.model:
            parser.error("provide --model or explicitly use --fixture")
        results = run_suite(args.tasks, args.platform, args.output, args.fixture, args.model, args.base_url, args.trials, args.split,
                            profiles=args.profiles, task_ids=args.task_ids, limit=args.limit, model_context=args.model_context,
                            model_output=args.model_output, timeout=args.timeout, seed=args.seed,
                            max_steps=args.max_steps, max_calls=args.max_calls, max_tokens=args.max_tokens)
        print(json.dumps({"trials": len(results), "fixture": args.fixture}))
    elif args.command == "report":
        print(json.dumps(report(args.output, args.include_fixtures), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(export_sft(args.output, args.destination)))


if __name__ == "__main__":
    main()
