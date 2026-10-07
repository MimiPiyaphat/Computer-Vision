"""Offline validation: never changes the live deployment threshold."""

import argparse
from src.threshold_validation import write_report
from src.research import load_parameters


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tuning", help="Labeled tuning pairs JSONL")
    parser.add_argument("holdout", help="Labeled customer-disjoint holdout pairs JSONL")
    parser.add_argument("--output", required=True, help="Research report JSON path")
    parser.add_argument("--minimum-sensitivity", type=float,
                        default=load_parameters()["targets"]["overall_sensitivity_stretch"],
                        help="Tuning sensitivity target; defaults to the university project's 0.86 stretch goal, not a clinical standard")
    parser.add_argument("--check-project-targets", action="store_true", help="Exit 3 if held-out sensitivity falls below the project floor")
    args = parser.parse_args()
    try:
        report = write_report(args.tuning, args.holdout, args.output, args.minimum_sensitivity)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Validation failed: {exc}\n")
    print(f"Research report saved to {args.output}; candidate is NOT approved for deployment.")
    print(f"Symptomatic holdout sensitivity: {report['holdout']['sensitivity']:.3f}")
    if args.check_project_targets and report["project_performance_targets"]["status"] != "met_on_this_sample":
        parser.exit(3)


if __name__ == "__main__":
    main()
