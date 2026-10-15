# Computer Architecture Assignments

## Assignment 1

```text
Assignment1/
├── BP/          # Branch prediction
└── Tomasulo/    # Multi-issue Tomasulo simulator
```

- **[BP](Assignment1/BP/)**: Pentium M style hybrid branch predictor, C++ source, tests, benchmark scripts, and saved results. See the [instructions](Assignment1/BP/README.md) and [PDF report](Assignment1/BP/Branch_Prediction_Report.pdf).
- **[Tomasulo](Assignment1/Tomasulo/)**: Python out-of-order simulator, tests, benchmarks, saved results, and assignment PDFs. See the [instructions](Assignment1/Tomasulo/README.md) and [PDF report](Assignment1/Tomasulo/Tomasulo_Assignment_Report.pdf).

## Quick start

For branch prediction, run from the repository root:

```sh
cd Assignment1/BP
make -C cbp2-infrastructure-v2/src all test
```

The branch-prediction traces are supplied separately by the course. Copy them to
`Assignment1/BP/cbp2-infrastructure-v2/traces/` before running trace benchmarks.

For Tomasulo, run from the repository root:

```sh
cd Assignment1/Tomasulo
python3 tomasulo-python/code/main.py
python3 -m unittest discover -s tests -v
```

Each project's README contains the full requirements and reproduction commands.

## Rebuild the PDF reports

The reports describe the implementation, checked results, and limitations for each problem:

- [Branch prediction report](Assignment1/BP/Branch_Prediction_Report.pdf) — 6 pages.
- [Tomasulo report](Assignment1/Tomasulo/Tomasulo_Assignment_Report.pdf) — 23 pages following the supplied sample's Introduction / Code Changes / Results format, with code comparisons and one result figure per issue width.

From the repository root, using Python 3.9 or newer:

```sh
python3 -m venv .report-venv
.report-venv/bin/pip install -r requirements-report.txt
.report-venv/bin/python scripts/build_assignment_reports.py
```

The builder checks the saved BP measurements against source checksums and reruns all
36 Tomasulo benchmarks against the sequential interpreter and saved outputs.
The numerical inputs remain in each project's `results/` folder.
