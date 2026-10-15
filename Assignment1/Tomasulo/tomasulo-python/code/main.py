"""Command-line entry point (Python 3.9+, standard library only)."""
import argparse
import json
from pathlib import Path

from init import read_program
from print_status import as_result, format_result
from simulator import Simulator


def main():
    parser = argparse.ArgumentParser(description="Multi-issue Tomasulo simulator")
    parser.add_argument("input", nargs="?", type=Path,
                        default=Path(__file__).with_name("test_case.txt"))
    parser.add_argument("--issue-width", type=int, choices=range(1, 5))
    parser.add_argument("--max-cycles", type=int, default=100000)
    parser.add_argument("--json", action="store_true", help="Print machine-readable results")
    parser.add_argument("--output", type=Path, help="Write results to a file")
    args = parser.parse_args()
    try:
        cpu = Simulator(read_program(args.input), args.issue_width).run(args.max_cycles)
        output = json.dumps(as_result(cpu), indent=2) + "\n" if args.json else format_result(cpu)
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
