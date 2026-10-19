"""Run validation and save reproducible benchmark traces, CSV, and JSON."""
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "code"))
sys.path.insert(0, str(BASE / "tests"))
from init import read_program
from print_status import format_result
from simulator import Simulator
from reference import interpret


def main():
    output = BASE / "results"
    output.mkdir(exist_ok=True)
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(BASE / "tests"))
    validation = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (output / "tests.txt").write_text(stream.getvalue())
    if not validation.wasSuccessful():
        print(stream.getvalue())
        return 1
    rows = []
    for path in sorted((BASE / "benchmarks").glob("*.in")):
        program = read_program(path)
        expected_registers, expected_memory, expected_trace = interpret(program)
        for width in range(1, 5):
            result = Simulator(program, width).run()
            committed_trace = [r["pc_bytes"] for r in result["instructions"] if r["status"] == "committed"]
            if (result["registers"], result["memory"], committed_trace) != (expected_registers, expected_memory, expected_trace):
                raise AssertionError(f"oracle mismatch: {path.stem}, width {width}")
            stem = f"{path.stem}_w{width}"
            (output / f"{stem}.json").write_text(json.dumps(result, indent=2) + "\n")
            (output / f"{stem}.txt").write_text(format_result(result) + "\n")
            rows.append(dict(benchmark=path.stem, width=width, cycles=result["cycles"],
                             ipc=round(result["ipc"], 6), **result["statistics"], verified=True))
    with (output / "summary.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    files = sorted([*BASE.glob("code/*.py"), *BASE.glob("tests/*.py"), *BASE.glob("benchmarks/*.in")])
    hashes = {str(path.relative_to(BASE)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    summary = dict(tests_passed=validation.testsRun, benchmark_runs=len(rows),
                   generated_programs=90, generated_width_comparisons=360,
                   source_sha256=hashes, results=rows)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"{validation.testsRun} test methods passed; {len(rows)} benchmark runs verified.")
    print(f"{'Benchmark':<22} {'W1':>5} {'W2':>5} {'W3':>5} {'W4':>5}")
    for name in sorted({row['benchmark'] for row in rows}):
        cycles = [row["cycles"] for row in rows if row["benchmark"] == name]
        print(f"{name:<22}" + "".join(f"{value:>6}" for value in cycles))
    return 0


if __name__ == "__main__":
    sys.exit(main())
