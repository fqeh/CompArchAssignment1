# Assignment 1: Pentium M style branch prediction

This project implements the assignment's required hybrid **branch direction**
predictor in `pm_predictor`: a 4,096-entry bimodal table and a tagged global
predictor with 512 sets and two ways. A global hit supplies the prediction;
otherwise the bimodal prediction is used. Both predictors learn from actual
conditional branch outcomes using two-bit saturating counters.

The implementation and measured results are explained in [the PDF report](Branch_Prediction_Report.pdf).
On all 20 supplied traces, the hybrid averages **7.260 MPKI**, compared with
86.312 for always-taken, 10.299 for bimodal, and 6.306 for the supplied gshare.
MPKI counts mispredictions per 1,000 instructions; lower is better.

## Requirements

- A C++ compiler (`g++` or Clang) and `make`.
- `bzip2` and `gzip`, used by the supplied trace decoder.
- Python 3.8 or newer for the comparison script; no third-party packages.
- `csh` and `dc` only if using the original `run` script.

The benchmark traces come from the course's `cbp2-infrastructure-v2` archive.
They are already present in the local assignment folder. For a fresh GitHub
checkout, copy the archive's `traces` directory to
`cbp2-infrastructure-v2/traces`. Course PDFs, trace data, and compiled binaries
are excluded from the source submission. The supplied decompressor paths are
defined near the top of `src/trace.h` if they differ on your system.

## Build and run

Run these commands from `Assignment1/BP`:

```sh
make -C cbp2-infrastructure-v2/src
cd cbp2-infrastructure-v2
./src/predict traces/164.gzip/gzip.trace.bz2
```

Expected output for that trace:

```text
12.617 MPKI
```

From `cbp2-infrastructure-v2`, the original assignment runner is also supported:

```sh
csh run traces
```

The legacy runner truncates its mean to three decimal places, so it prints
`7.259`; the exact aggregate rounded to three decimal places is `7.260`.

## Tests and reproducible comparison

From `Assignment1/BP`:

```sh
make -C cbp2-infrastructure-v2/src test
make -C cbp2-infrastructure-v2/src sanitize
python3 scripts/benchmark.py
```

The sanitizer target requires compiler support for AddressSanitizer and
UndefinedBehaviorSanitizer. Both test commands print
`PASS: 7 predictor test groups` when successful.

The benchmark script builds its evaluator, runs all four predictors on each
trace, and independently checks every hybrid MPKI against `src/predict`.
It regenerates:

- [results/benchmark-summary.md](results/benchmark-summary.md): all 20 comparisons.
- [results/benchmark.csv](results/benchmark.csv): exact miss counts, MPKI,
  global hit rates, and trace checksums.
- [results/driver-results.txt](results/driver-results.txt): checked driver output.
- [results/environment.txt](results/environment.txt): environment and source checksums.

Each trace represents 100 million instructions. Each process starts with fresh
predictor state, and the results include initial training. The last CSV row
contains aggregate counts and aggregate MPKI, which equals the arithmetic mean
of trace MPKIs because all traces have the same instruction count.

## Files

| File | Purpose |
| --- | --- |
| `cbp2-infrastructure-v2/src/my_predictor.h` | Required hybrid implementation and supplied predictor classes |
| `cbp2-infrastructure-v2/src/predict.cc` | Original assignment driver |
| `cbp2-infrastructure-v2/tests/predictor_test.cc` | Counter, lookup, replacement, history, and pattern tests |
| `cbp2-infrastructure-v2/tests/evaluate.cc` | Four-predictor trace evaluator |
| `scripts/benchmark.py` | Reproduce and verify the reported measurements |
| `Branch_Prediction_Report.pdf` | Design, assumptions, results, analysis, and references |

The required work predicts taken/not taken. As permitted by the handout, it
omits the loop predictor, target prediction, and Pentium M path information
register. The optional `cpm_predictor` extra-credit skeleton is unchanged and
does not implement the complete Pentium M unit. `make` still builds that
original optional driver, but use `predict` for this submission.

The supplied decoder and driver can emit legacy compiler warnings on newer
Clang versions (`sprintf` deprecation and an unused target-miss count).
The required predictor and tests compile and run successfully.

## Attribution

The simulator, trace reader, gshare example, original documentation, and runner
were supplied with the course infrastructure credited to Daniel A. Jiménez.
The hybrid implementation follows the assignment handout. No external cache
implementation was used. See the report for design references and tool assistance.

## Rebuild the PDF

See the [repository PDF instructions](../../README.md#rebuild-the-pdf-reports).
The report covers the implementation, all 20 trace results, tests, limitations,
and reproduction commands.
