#!/usr/bin/env python3
"""Reproduce the four-predictor comparison using the course's 100M-instruction traces."""
import csv
import hashlib
import io
import platform
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INFRA = ROOT / "cbp2-infrastructure-v2"
PREDICTORS = ("always_taken", "bimodal", "gshare", "hybrid")
INSTRUCTIONS = 100_000_000


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def main():
    subprocess.run(["make", "-C", "src", "evaluate", "predict"], cwd=INFRA, check=True)
    traces = sorted((INFRA / "traces").glob("*/*.trace.*"))
    if not traces:
        raise SystemExit("No traces found. Restore cbp2-infrastructure-v2/traces from the course archive.")
    rows = []
    driver_lines = []
    for path in traces:
        relative = path.relative_to(INFRA).as_posix()
        # The original course decoder passes filenames to a shell command.
        # The distributed relative names contain no spaces or shell syntax.
        if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/._-" for c in relative):
            raise SystemExit("Use the original course trace directory and filenames.")
        result = subprocess.run(["./src/evaluate", relative], cwd=INFRA,
                                check=True, capture_output=True, text=True)
        if result.stderr:
            raise RuntimeError(result.stderr)
        records = list(csv.DictReader(io.StringIO(result.stdout)))
        if len(records) != 1:
            raise RuntimeError(f"Unexpected evaluator output for {relative}")
        row = {key: int(value) for key, value in records[0].items()}
        if row["conditional_branches"] == 0:
            raise RuntimeError(f"No conditional branches decoded from {relative}")
        row.update(benchmark=path.parent.name, instructions=INSTRUCTIONS,
                   trace_sha256=digest(path))
        for name in PREDICTORS:
            row[f"{name}_mpki"] = row[f"{name}_misses"] * 1000.0 / INSTRUCTIONS
        row["global_hit_rate_percent"] = row["global_hits"] * 100.0 / row["conditional_branches"]

        # Independently run the assignment driver and check its rounded MPKI.
        driver = subprocess.run(["./src/predict", relative], cwd=INFRA,
                                check=True, capture_output=True, text=True)
        if driver.stderr or driver.stdout.strip() != f"{row['hybrid_mpki']:.3f} MPKI":
            raise RuntimeError(f"Driver/evaluator mismatch for {relative}: {driver.stdout} {driver.stderr}")
        driver_lines.append(f"{relative:<42} {driver.stdout.strip()}")
        rows.append(row)
        print(f"{row['benchmark']:<15} " + "  ".join(
            f"{name}={row[f'{name}_mpki']:.3f}" for name in PREDICTORS), flush=True)

    total = {"benchmark": "ALL", "instructions": len(rows) * INSTRUCTIONS,
             "trace_sha256": ""}
    for key in ("conditional_branches", "global_hits", *(f"{p}_misses" for p in PREDICTORS)):
        total[key] = sum(row[key] for row in rows)
    for name in PREDICTORS:
        total[f"{name}_mpki"] = total[f"{name}_misses"] * 1000.0 / total["instructions"]
    total["global_hit_rate_percent"] = total["global_hits"] * 100.0 / total["conditional_branches"]

    output = ROOT / "results"
    output.mkdir(exist_ok=True)
    fields = ["benchmark", "instructions", "conditional_branches"]
    for name in PREDICTORS:
        fields += [f"{name}_misses", f"{name}_mpki"]
    fields += ["global_hits", "global_hit_rate_percent", "trace_sha256"]
    with (output / "benchmark.csv").open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        for row in [*rows, total]:
            writer.writerow({key: f"{value:.6f}" if isinstance(value, float) else value
                             for key, value in row.items()})

    table = ["# Benchmark results", "",
             "MPKI = conditional direction mispredictions per 1,000 instructions. Lower is better.", "",
             "| Benchmark | Always taken | Bimodal | Gshare | Hybrid | Global hit rate |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in [*rows, total]:
        label = "**Average / aggregate**" if row is total else row["benchmark"]
        table.append("| " + label + " | " + " | ".join(
            f"{row[f'{p}_mpki']:.3f}" for p in PREDICTORS)
            + f" | {row['global_hit_rate_percent']:.2f}% |")
    table += ["", "Each trace represents 100,000,000 instructions. The final MPKI values are",
              "arithmetic means because all traces have equal instruction counts. The final",
              "global hit rate is weighted by the number of conditional branches.", "",
              "All hybrid MPKI values were checked against the separate assignment driver.",
              "Exact miss counts and trace SHA-256 checksums are in `benchmark.csv`.", ""]
    (output / "benchmark-summary.md").write_text("\n".join(table))
    driver_lines.append(f"average MPKI: {total['hybrid_mpki']:.3f}")
    (output / "driver-results.txt").write_text("\n".join(driver_lines) + "\n")

    compiler = subprocess.run(["g++", "--version"], check=True, capture_output=True, text=True).stdout
    metadata = [f"Platform: {platform.system()} {platform.release()} ({platform.machine()})",
                f"Python: {platform.python_version()}", f"Traces: {len(rows)}",
                "Build: make -C cbp2-infrastructure-v2/src evaluate predict",
                "Default flags: -g -O3 -Wall", "", compiler.strip(), "", "Source SHA-256:"]
    for relative in ("scripts/benchmark.py", "cbp2-infrastructure-v2/tests/evaluate.cc",
                     "cbp2-infrastructure-v2/src/my_predictor.h",
                     "cbp2-infrastructure-v2/src/predict.cc", "cbp2-infrastructure-v2/src/trace.cc"):
        metadata.append(f"{digest(ROOT / relative)}  {relative}")
    (output / "environment.txt").write_text("\n".join(metadata) + "\n")
    print("Average MPKI: " + ", ".join(f"{p}={total[f'{p}_mpki']:.3f}" for p in PREDICTORS))
    print(f"Saved results to {output}")


if __name__ == "__main__":
    main()
