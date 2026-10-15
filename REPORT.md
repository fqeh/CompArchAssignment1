# Assignment 1: Branch Predictor Implementation

## Objective and scope

The completed `pm_predictor` simulates the hybrid branch direction predictor
required by the assignment: a bimodal predictor combined with a tagged global
predictor. It predicts whether a conditional branch is taken and learns after
the simulator supplies its actual outcome.

The implementation uses the handout's permitted two-way global organization.
It omits the loop predictor, branch target prediction, and Pentium M path
information register (PIR), as explicitly allowed. This is a functional
simulation of the assigned subset, not a cycle-accurate model of the complete
Pentium M processor. The optional extra-credit `cpm_predictor` remains the
provided skeleton.

## Predictor organization

| Structure | Configuration |
| --- | --- |
| Bimodal table | 4,096 two-bit counters, indexed by branch address bits `[11:0]` |
| Global table | 512 sets, two ways per set, 1,024 entries total |
| Global entry | Valid bit, six-bit tag, two-bit counter |
| Global history register (GHR) | Most recent 15 conditional outcomes; initial value zero |
| Replacement | Least recently used (LRU), represented by one victim bit per set |
| Cold bimodal counters | `1`, weakly not taken |
| Cold global entries | Invalid; counters initialized to `1` |
| New global entry | `2` after taken, `1` after not taken |

The global set count, tag size, and bimodal capacity follow the assignment's
diagrams. The history length, initialization, and training policy are explicit
implementation choices. Appendix B illustrates the mechanism using smaller
tables and varied initial counter values; this implementation uses uniform
initialization for reproducibility.

The simplified global access function is:

```text
bimodal_index = address & 0xFFF
hash          = (address XOR GHR) & 0x7FFF
global_set    = hash >> 6
global_tag    = hash & 0x3F
```

This uses a gshare-style XOR of address and outcome history in place of the
optional PIR and its hash. The 15-bit hash supplies nine set bits and six tag
bits. The implementation retains byte-address bits, consistent with the main
diagram's bimodal index `IP[11:0]`; it does not assume word-aligned branches.

The tag distinguishes different hashes mapping to the same set. It does not
eliminate all aliasing: different address/history combinations can still
produce the same 15-bit hash.

## Prediction and update

`predict()` saves whether the branch is conditional, the bimodal index, global
set and tag, and the matching way, if any, in a `pm_update` object. It does not
train counters or shift the history register.

For a conditional branch, a valid matching global entry supplies the final
prediction. On a global miss, the bimodal table supplies the final prediction.
Counter values `0` and `1` predict not taken; `2` and `3` predict taken. The
global prediction has priority even when the bimodal prediction disagrees.
There is no separate chooser table.

After the outcome is known, `update()` performs these operations:

1. Train the saved bimodal counter for every conditional branch.
2. On a global hit, train the matching counter. On a miss, allocate a new entry,
   preferring an invalid way and otherwise replacing the LRU way. Initialize
   its counter weakly toward the observed outcome instead of inheriting the
   victim's counter. Allocation occurs on every global miss, including when
   the bimodal prediction was correct.
3. Mark the touched global way as most recently used; the other way becomes
   the next replacement candidate.
4. Shift the actual outcome into the GHR and mask it to 15 bits:
   `GHR = ((GHR << 1) | taken) & 0x7FFF`.

Training increments a counter on taken, up to `3`, and decrements it on not
taken, down to `0`. Saving the original lookup information ensures that the
outcome trains the entry consulted before the history change.

Unconditional branches are predicted taken and do not update these direction
tables or outcome history. Target predictions are set to zero because they
are outside the required scope. A single update object is sufficient because
the supplied driver calls `predict()` and then `update()` for each branch
before reading the next one.

## Storage estimate

The logical hardware state, excluding simulator bookkeeping, is:

```text
Bimodal counters:           4,096 × 2         =  8,192 bits
Global valid/tag/counter:     512 × 2 × 9     =  9,216 bits
Two-way LRU state:            512 × 1         =    512 bits
Global history:                                =     15 bits
Total:                                           17,935 bits
```

That is 2,242 bytes when rounded up, approximately 2.19 KiB. This is a logical
bit-storage estimate: the C++ implementation uses byte-sized counters and
fields, and also stores the update record and object bookkeeping.

The supplied gshare contains 32,768 two-bit counters and 15 history bits,
or 65,551 logical bits (8,194 bytes rounded up). Its comparison with the hybrid
is therefore not an equal-storage experiment.

## Experimental method

All 20 distributed traces were evaluated. According to the supplied
infrastructure documentation, each represents 100,000,000 instructions, so the
experiment covers 2,000,000,000 instructions. The decoder yielded 275,461,634
conditional branches in total.

Four predictors were compared on the same decoded stream:

- **Always taken:** equivalent to the original `pm_predictor` placeholder.
- **Bimodal:** 4,096 two-bit counters initialized to weakly not taken and
  updated on every conditional branch, matching the hybrid's bimodal part.
- **Gshare:** the supplied 32,768-entry, 15-history-bit implementation,
  including its original strongly-not-taken initialization.
- **Hybrid:** the completed `pm_predictor` described above.

Each trace starts in a separate process with fresh state. There is no excluded
warm-up period, no benchmark-specific configuration, and no parameter tuning
between traces. Only conditional direction errors are counted:

```text
MPKI = direction_mispredictions × 1,000 / instructions
```

MPKI is not the percentage of branches mispredicted. For an individual supplied
trace, its denominator is 100 million instructions rather than the number of
branch records. The mean is computed from exact miss counts before rounding.

`scripts/benchmark.py` runs the comparison evaluator and separately runs the
original assignment driver for every trace. All 20 hybrid results agreed at
the driver's three-decimal precision. The script records raw counts, SHA-256
checksums of traces and relevant source files, and the compiler environment.
The measurements were made on macOS/arm64 using Apple Clang 17.0.0 through
`g++`, with the supplied `-g -O3 -Wall` flags.

## Results and discussion

| Predictor | Total direction errors | Average MPKI |
| --- | ---: | ---: |
| Always taken | 172,623,375 | 86.312 |
| Bimodal | 20,597,217 | 10.299 |
| Supplied gshare | 12,611,718 | 6.306 |
| Implemented hybrid | 14,519,207 | 7.260 |

The full per-trace table is in
[results/benchmark-summary.md](results/benchmark-summary.md), and exact counts
are in [results/benchmark.csv](results/benchmark.csv).

The hybrid reduces mean MPKI by **91.59%** relative to always-taken and
**29.51%** relative to bimodal. It improves on bimodal in **19 of 20** traces.
For example, `181.mcf` improves from 33.245 to 17.680 MPKI, and `202.jess`
improves from 8.809 to 1.750. These results are consistent with outcome history
capturing behavior that a single counter per branch address cannot represent.

The global table supplies 203,900,607 predictions, or **74.02%** of all
conditional predictions. The remaining predictions use the bimodal fallback.
This is a lookup hit rate, not an accuracy rate. Both useful and incorrect
global predictions count as hits.

The hybrid does not outperform every alternative. Its mean MPKI is **15.12%
higher** than the supplied gshare's, and it beats gshare on only `256.bzip2`
(0.076 versus 0.094 MPKI). Gshare has substantially more counter storage and
different cold initialization. Global capacity, replacement, hash aliasing,
and unconditional global-hit priority are plausible contributors to the
hybrid's remaining errors; the experiment does not isolate their individual
effects. An equal-storage comparison would be needed to attribute the gap to
predictor organization alone.

`300.twolf` is also a small regression against bimodal: 22.046 versus 21.942
MPKI. Its global hit rate is only 32.68%, and a global hit always overrides the
bimodal result, so adding the global table is not guaranteed to improve every
workload. The very low error rate on `256.bzip2` demonstrates the opposite
case: its 99.62% global hit rate accompanies strong prediction accuracy.

The provided `baseline-results.txt` is preserved. Its per-trace always-taken
values match the fresh measurements. Its printed average is truncated by the
legacy `dc` runner; the report instead rounds the exact aggregate. The same
distinction explains why `csh run traces` prints a hybrid mean of `7.259`
while the report shows `7.260`.

## Validation and reproduction

The seven deterministic test groups cover:

1. Cold invalid entries, zero tags, bimodal fallback, and prediction without training.
2. Hand-computed address/history indices, maximum addresses, and byte-address distinctions.
3. Every two-bit counter transition, saturation, both global ways, and global-hit priority.
4. Invalid-entry preference, LRU refresh and eviction, and counter reinitialization on replacement.
5. Training the saved pre-update index and shifting/masking actual outcome history.
6. Ignoring unconditional jumps, calls, returns, and indirect branches when training direction state.
7. Learning sustained taken, sustained not-taken, and alternating outcome patterns.

The tests passed in both the optimized build and a build with AddressSanitizer
and UndefinedBehaviorSanitizer. The full trace comparison and independent
driver checks also completed successfully.

From the repository root:

```sh
make -C cbp2-infrastructure-v2/src all test sanitize
python3 scripts/benchmark.py
```

No third-party Python packages or external cache library are required. The
course traces must be restored from the assignment archive in a fresh checkout;
they are not included in the source submission. `README.md` describes the
single-trace and original-runner commands.

## References and attribution

1. **Assignment 1: Branch Predictor Implementation**, supplied
   `programming-branch-predictor.pdf`, especially pages 2 and 5–11. The required
   subset, table structure, two-way allowance, and worked example come from
   this handout.
2. **Daniel A. Jiménez, Infrastructure for Branch Prediction Competition**,
   supplied `cbp2-infrastructure-v2/doc/index.html` and source distribution.
   The driver, decoder, sample gshare predictor, and original scripts are
   provided infrastructure. The decoder's command pointer was made `const`
   to correctly hold its string literals; the decoding algorithm is unchanged.
3. **Vladimir Uzelac and Aleksandar Milenković (2009), Experiment Flows and
   Microbenchmarks for Reverse Engineering of Branch Predictor Structures**,
   ISPASS, pp. 207–217, DOI: 10.1109/ISPASS.2009.4919652.
   [Author-hosted paper](https://alexmilenkovich.github.io/publications/files/vuam_ispass09.pdf).
   This is the Pentium M background reference named by the handout. The local
   `milenkovic_WDDD02.pdf` is a different, earlier paper about Pentium III/4;
   it was not treated as the Pentium M implementation specification.

No external cache implementation was copied. Codex assisted with implementation,
tests, benchmark execution, and documentation. Reported measurements come from
executing the included code on the supplied traces.
