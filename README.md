# Computer Architecture Assignments

## Assignment 1

```text
Assignment1/
├── BP/          # Branch prediction
└── Tomasulo/    # Multi-issue Tomasulo simulator
```

- **[BP](Assignment1/BP/)**: Pentium M style hybrid branch predictor, C++ source, tests, benchmark scripts, and saved results. See the [instructions](Assignment1/BP/README.md) and [report](Assignment1/BP/REPORT.md).
- **[Tomasulo](Assignment1/Tomasulo/)**: Python out-of-order simulator, tests, benchmarks, saved results, and assignment PDFs. See the [instructions](Assignment1/Tomasulo/README.md) and [report](Assignment1/Tomasulo/REPORT.md).

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
