# Computer Architecture Assignments

**Ali Alfageeh**

## Tomasulo

The Tomasulo assignment is in [`tomasulo/`](tomasulo/).

- [Assignment report](tomasulo/Tomasulo_Assignment_Report_Ali_Alfageeh.pdf)
- [Simulator and run instructions](tomasulo/README.md)

Requires Python 3.10 or later. From the repository root:

```bash
python3 tomasulo/code/main.py
```

## Branch prediction

The branch prediction assignment is in [`branch-prediction/`](branch-prediction/).
It implements a Pentium M-style hybrid direction predictor and compares it
with bimodal, gshare, and always-taken predictors.

- [Assignment report](branch-prediction/report/Ali_Alfageeh_Branch_Prediction_Report.pdf)
- [Build, test, and benchmark instructions](branch-prediction/README.md)
- [Recorded benchmark results](branch-prediction/results/benchmark_summary.txt)

Requires a C++17 compiler, Make, Python 3, gzip, and bzip2. From the repository root:

```bash
cd branch-prediction
make -C src
make -C src test
```

The folder includes source, tests, the final report, and recorded results.
The tests generate their own inputs. To rerun the full benchmarks, obtain the
original course traces and place them under `branch-prediction/traces/` as
described in the project README. Trace data and compiled binaries are not
committed.
