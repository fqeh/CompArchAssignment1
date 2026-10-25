# Branch Prediction Assignment

**Assignment author: Ali Alfageeh**

I implemented the required Pentium M-style direction predictor in
[`src/my_predictor.h`](src/my_predictor.h) using the supplied CBP2 infrastructure.
Read the [assignment report](report/Ali_Alfageeh_Branch_Prediction_Report.pdf)
and [recorded benchmark summary](results/benchmark_summary.txt).

This project is published in the `branch-prediction/` folder of
[`fqeh/CompArchAssignment1`](https://github.com/fqeh/CompArchAssignment1).

## Build and run

Requirements: C++17 compiler (`g++`), GNU Make, Python 3, gzip and bzip2.
The simulator and tests have no third-party Python package dependencies.
Run these commands from the repository root:

```sh
cd branch-prediction
make -C src
make -C src test
```

The tests generate their own small inputs, so no benchmark traces are needed
to build or test the project. All subsequent commands assume you are in
`branch-prediction/`.

The original course traces are not included in the GitHub folder. To reproduce
the full evaluation, copy the supplied trace collection into `traces/`, keeping
paths such as `traces/164.gzip/gzip.trace.bz2`. The trace directory is ignored by
Git. Use a directory inside this project so the benchmark script can record
relative paths in its provenance file.

```sh
./src/predict traces/164.gzip/gzip.trace.bz2
./run traces
```

`predict TRACE` uses the completed hybrid and retains the original `MPKI`
output. The portable `run` script evaluates all 20 traces with four predictors
and writes exact counts, MPKI and accuracy to `results/`.

```sh
./src/predict traces/164.gzip/gzip.trace.bz2 --predictor pm --json
python3 scripts/benchmark.py --jobs 4
```

`--predictor` accepts `pm`, `bimodal`, `gshare`, and `always_taken`.
`--instructions N` overrides the default 100,000,000-instruction denominator
for custom traces whose instruction count is known. It does not limit the
number of branches simulated. Input is the CBP2 binary trace format (plain,
gzip or bzip2); arbitrary text traces are not supported.

## My implementation

- Bimodal: 4,096 two-bit saturating counters; index `PC & 0xfff`.
- Global: 512 sets, two ways, valid bit, six-bit tag and two-bit counter.
- History: 15 actual conditional outcomes; starts at zero.
- Hash: `(PC ^ GHR) & 0x7fff`; set `HASH[14:6]`; tag `HASH[5:0]`.
- A valid tag hit selects global prediction; otherwise I use bimodal.
- Both components learn from each conditional branch; local counters start
  weakly not taken (1). A missing global tag is allocated after resolution,
  initialized to weakly taken (2) or weakly not taken (1) from the outcome.
- Invalid ways are allocated first. A full set uses true two-way LRU.
- Nonconditional branches predict taken and do not train tables or GHR.
- Prediction-time indices are saved before the GHR is updated.

The 15-bit outcome GHR and XOR are the documented simplified history/hash
choice allowed by the assignment. This is not a cycle-accurate reconstruction
of Intel's proprietary predictor. Loop prediction, target prediction, PIR,
and the extra-credit full predictor are outside the required scope.
The supplied `cpm_predictor` remains an unimplemented extra-credit skeleton;
`make` does not build or use it. The optional `make -C src extra` only builds
that original skeleton and does not represent a completed extension.

The driver predicts one branch and immediately resolves it, as in CBP2.
Multiple unresolved branches and speculative rollback are not modeled.
Raw PC bits follow the full assignment diagram; the reduced Appendix B
example uses shifted addresses and patterned initial counters, so its tables
are not a numerical oracle for this default configuration.

## Verification

```sh
make -C src test
ASAN_OPTIONS=detect_leaks=0 make -C src sanitize
python3 scripts/benchmark.py --jobs 4
python3 tests/test_baseline_equivalence.py
```

There are 16 predictor tests, including an independent 250,000-event reference
model, plus 9 end-to-end driver tests. The benchmark and baseline-equivalence
commands require the original 20 course traces in `traces/`.
The baseline-equivalence script compiles
the actual starter source and checks 40 original-binary results across all
20 traces (always taken and supplied gshare). AddressSanitizer and UBSan are
used; LeakSanitizer is disabled in the recorded run because the container
cannot inspect the process tree. The original environment failure is retained
in `results/sanitizers_environment_note.txt`.

To regenerate the deterministic walkthrough:

```sh
g++ -std=c++17 -O2 -Isrc tests/walkthrough.cc -o /tmp/branch-walkthrough
/tmp/branch-walkthrough > results/walkthrough.csv
```

## Measured results

The recorded evaluation ran each predictor on the same 20 cold-start traces,
representing two billion instructions and 275,461,634 conditional branches in
total. These measurements come from the original Linux run, and the report
presents those recorded results;
[`results/provenance.json`](results/provenance.json) records its environment
and source/trace hashes. The published trace reader additionally resolves
`gzip`, `bzip2`, and `cat` through `PATH` for macOS/Linux portability, so its
header differs from the historical hash. Predictor logic is unchanged.

| Predictor | Total direction misses | MPKI | Conditional accuracy |
|---|---:|---:|---:|
| always_taken | 172,623,375 | 86.311688 | 37.3331% |
| bimodal | 20,597,217 | 10.298609 | 92.5227% |
| gshare | 12,611,718 | 6.305859 | 95.4216% |
| pm | 14,519,207 | 7.259603 | 94.7291% |

The hybrid reduces misses by 29.51% versus the matched bimodal-only control
and wins on 19 of 20 traces. It has 15.12% more misses than the supplied,
larger 32,768-entry gshare baseline. The comparison is not storage-normalized:
logical state is 17,935 bits for my hybrid, 8,192 for bimodal and 65,551 for
gshare including its 15-bit history. C++ storage uses byte-sized counters and
object overhead, so `sizeof(pm_predictor)` is 7,744 bytes in the tested build.

## Files and provenance

- [`src/`](src/): completed implementation, driver and trace decoder.
- [`tests/`](tests/): behavioral, randomized reference, CLI and baseline checks.
- [`scripts/benchmark.py`](scripts/benchmark.py): full evaluation with CSV/JSON output.
- [`results/`](results/): recorded measurements, test logs, walkthrough and provenance.
- [`report/`](report/): final assignment PDF.
- [`baseline/`](baseline/): original supplied source and runner for comparison.
- [`changes.patch`](changes.patch): source and runner differences against the starter.
- [`doc/index.html`](doc/index.html): original CBP2 infrastructure documentation.

The baseline remains the original course source, including its Linux command
paths. Run baseline-equivalence checks on Linux with the original traces.
The final PDF includes the source snapshots and measured results; separate
report-generation assets are not needed to build or run the predictor.

The original CBP2 infrastructure and gshare example are supplied course code.
The infrastructure documentation credits Daniel A. Jimenez. My author label
covers the assignment implementation, new tests, experiment scripts and report;
original source attribution is retained. No third-party cache code was copied.

## GitHub submission

The GitHub folder includes the source, build files, tests, benchmark runner,
recorded results, final report and original attribution. Bulk traces, reference
PDFs, generated images/fonts, duplicate documentation, unused utilities and
compiled binaries are excluded. `.gitignore` keeps local traces and build
outputs out of future commits.
