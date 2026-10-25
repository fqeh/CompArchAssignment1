#!/usr/bin/env python3
"""Tomasulo assignment entry point. Author: Ali Alfageeh.

Starter attribution: Qing, May 2017. See original/tomasulo-python/ for original files.
"""
import argparse
import json
import math
from pathlib import Path
import sys
from init import parse_program
from simulator import Simulator
from print_status import format_result


def json_safe(value):
    """Keep JSON standards-compliant without changing numeric simulator state.

    IEEE non-finite results are explicit strings: NaN, Infinity, -Infinity.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return 'NaN' if math.isnan(value) else ('Infinity' if value > 0 else '-Infinity')
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description='Tomasulo simulator - Ali Alfageeh')
    parser.add_argument('input', nargs='?', default=str(Path(__file__).with_name('code.in')))
    parser.add_argument('--issue-width', type=int, choices=range(1, 5))
    parser.add_argument('--json', type=Path, help='also save the complete result as JSON')
    parser.add_argument('--legacy-branch-bytes', action='store_true', help='interpret branch offsets as bytes (starter compatibility)')
    parser.add_argument('--max-cycles', type=int, default=100000)
    args = parser.parse_args(argv)
    try:
        program = parse_program(Path(args.input).read_text(), args.legacy_branch_bytes)
        result = Simulator(program, args.issue_width, args.max_cycles).run()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    print(format_result(result), end='')
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
