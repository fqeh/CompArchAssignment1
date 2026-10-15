"""Regenerate all report measurements and full traces using the ISA oracle."""
import csv
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tomasulo-python" / "code"))
sys.path.insert(0, str(ROOT / "tests"))
from init import read_program
from print_status import format_result
from reference import execute
from simulator import Simulator


def main():
    directory = ROOT / "results"
    directory.mkdir(exist_ok=True)
    rows = []
    states = {}
    table = ["| Benchmark | Width 1 | Width 2 | Width 3 | Width 4 | Speedup (1/4) |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for path in sorted((ROOT / "benchmarks").glob("*.txt")):
        program = read_program(path)
        expected_registers, expected_memory, expected_trace = execute(program)
        times = []
        for width in range(1, 5):
            cpu = Simulator(program, width).run()
            if (cpu.registers != expected_registers or cpu.memory != expected_memory
                    or [e.pc for e in cpu.committed] != expected_trace):
                raise RuntimeError(f"Oracle mismatch: {path.name}, width {width}")
            times.append(cpu.cycle)
            rows.append({"benchmark": path.stem, "issue_width": width,
                         "cycles": cpu.cycle, "committed": len(cpu.committed),
                         "mispredictions": cpu.mispredictions,
                         "memory_replays": cpu.memory_replays})
            (directory / f"{path.stem}_w{width}.txt").write_text(format_result(cpu), encoding="utf-8")
        states[path.stem] = {
            "registers_nonzero": {key: value for key, value in expected_registers.items() if value},
            "memory_nonzero": {key: value for key, value in expected_memory.items() if value},
            "committed_instructions": len(expected_trace),
        }
        table.append(f"| {path.stem} | " + " | ".join(map(str, times))
                     + f" | {times[0] / times[-1]:.2f}x |")
    summary = "\n".join(table) + "\n"
    (directory / "summary.md").write_text(summary, encoding="utf-8")
    (directory / "final_states.json").write_text(json.dumps(states, indent=2) + "\n", encoding="utf-8")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    (directory / "summary.csv").write_text(buffer.getvalue(), encoding="utf-8")
    report = ROOT / "REPORT.md"
    if report.exists():
        text = report.read_text(encoding="utf-8")
        begin, end = "<!-- RESULTS START -->", "<!-- RESULTS END -->"
        if begin in text and end in text:
            text = text.split(begin)[0] + begin + "\n\n" + summary + "\n" + end + text.split(end)[1]
            report.write_text(text, encoding="utf-8")
    print(summary, end="")
    print(f"Verified {len(rows)} runs against the sequential oracle.")


if __name__ == "__main__":
    main()
