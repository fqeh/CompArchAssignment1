"""Command-line entry point. Run python3 main.py --help for options."""
import argparse
import json
from pathlib import Path
import sys
from init import read_program
from print_status import format_result
from simulator import Simulator


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tomasulo simulator with in-order issue width 1-4")
    parser.add_argument("input", nargs="?", type=Path, default=Path(__file__).with_name("code.in"))
    parser.add_argument("--issue-width", type=int, choices=range(1, 5), help="override input issue width")
    parser.add_argument("--max-cycles", type=int, default=100000)
    parser.add_argument("--json", type=Path, help="write the complete result and dynamic trace as JSON")
    args = parser.parse_args(argv)
    try:
        result = Simulator(read_program(args.input), args.issue_width).run(args.max_cycles)
        print(format_result(result))
        if args.json:
            args.json.write_text(json.dumps(result, indent=2) + "\n")
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
