"""Extract authorized local YFP data or evaluate single-video facial scores."""

import argparse
import hashlib
import json
from pathlib import Path
from src.yfp_benchmark import extract, load_scores, benchmark


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    extraction = commands.add_parser("extract")
    extraction.add_argument("--manifest", required=True)
    extraction.add_argument("--data-root", required=True)
    extraction.add_argument("--output", required=True)
    evaluation = commands.add_parser("evaluate")
    evaluation.add_argument("--scores", required=True)
    evaluation.add_argument("--mode", choices=("fixed", "holdout", "lopo"), default="fixed")
    evaluation.add_argument("--fixed-threshold", type=float, default=.1,
                            help="Unfitted absolute single-video score cutoff; never a pre/post delta cutoff")
    evaluation.add_argument("--output", required=True)
    evaluation.add_argument("--check-targets", action="store_true", help="Exit 3 if both face targets are not demonstrated")
    args = parser.parse_args()
    try:
        if args.command == "extract":
            records = extract(args.manifest, args.data_root, args.output)
            print(f"Extracted {len(records)} samples; {sum(r['score'] is None for r in records)} unavailable. No media copied.")
            return
        report = benchmark(load_scores(args.scores), args.mode, args.fixed_threshold)
        report["input_sha256"] = hashlib.sha256(Path(args.scores).read_bytes()).hexdigest()
        Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        print(f"Facial benchmark: {report['targets']['status']}; overall stroke sensitivity remains unmeasured.")
        if args.check_targets and report["targets"]["status"] != "met_on_this_sample":
            parser.exit(3)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Benchmark failed: {exc}\n")


if __name__ == "__main__":
    main()
