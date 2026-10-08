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
    args = parser.parse_args()
    if args.command == "run":
        if not args.fixture and not args.model:
            parser.error("provide --model or explicitly use --fixture")
        results = run_suite(args.tasks, args.platform, args.output, args.fixture, args.model, args.base_url, args.trials, args.split)
        print(json.dumps({"trials": len(results), "fixture": args.fixture}))
    elif args.command == "report":
        print(json.dumps(report(args.output, args.include_fixtures), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(export_sft(args.output, args.destination)))


if __name__ == "__main__":
    main()
