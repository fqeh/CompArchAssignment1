# Verification workloads

Assignment implementation author: **Ali Alfageeh**.

Run from the package root with Python 3.10 or newer:

```sh
python3 -m unittest discover -s tests -v
python3 tests/run_benchmarks.py
```

The unittest suite checks architectural state and committed instruction order against
`oracle.py`, an independent sequential interpreter that does not import the simulator
parser or pipeline. It also checks hand-calculated register/memory answers, explicit
timing contracts, input validation and the command-line interface. Thirty deterministic
random straight-line programs are checked at all four widths (120 comparisons).
The seed is 20261025; each random program has 35 instructions. Ten additional
random programs contain overlapping byte-addressed memory operations and delayed
base addresses, each checked at four widths (40 comparisons; seed 180032).
The complete suite contains 38 unittest methods.

`run_benchmarks.py` executes each of the sixteen saved workloads at widths 1, 2, 3 and 4
through the CLI. It checks all registers, nonzero memory and committed control flow,
then saves actual text/JSON outputs plus `results/summary.csv` and `summary.json`.
Every summary row includes the exact input's SHA-256 digest. Memory checks compare
all 256 backing bytes exactly, as well as the displayed float views.

| Input | Purpose | Independently checked result |
|---|---|---|
| `sample_01.in` | Exact inputs from sample report Test Case 01 | R1=28; F1=5; F2=25; F3=0; F4=26 |
| `sample_02.in` | Exact inputs from sample report Test Case 02, including multiple FUs | R1=24; F1=6; F2=36; F3=0; F4=37 |
| `starter_equivalent.in` | Supplied starter program's legacy branch behavior, expressed in word offsets | R1=0; R2=20; Mem[32]=7; F20=2 |
| `daxpy_loop.in` | Three complete DAXPY iterations using a -8-word branch | Mem[24]=15; Mem[28]=11; Mem[32]=7; F20=6 |
| `rename_hazards.in` | Same-bundle RAW, WAW, WAR and immutable R0 | R1=9; R2=10; R3=R4=1; F1=4; F4=8; F5=4 |
| `structural_stalls.in` | One FP-adder RS and three ROB entries block younger issue | In-order issue preserved; F6=48; R2=3 |
| `store_forwarding.in` | Two older stores alias a load | Youngest store forwards F3=7 in one MEM cycle |
| `memory_replay.in` | A completed load has bypassed an unresolved older store | Replay occurs; F2=7; F3=14 |
| `branch_squash.in` | BEQ/BNE mispredictions with wrong-path store and register writes | Mem[0]=3; R2=7; R3=8 |
| `btb_collision_loop.in` | Branches at word PCs 2 and 10 share BTB index 2 | R2=3; R3=3; R9=0 |
| `parallel_fp.in` | Two FP adders and multipliers contend for one CDB | F7=11; F8=15; F9=18 |
| `case_and_boundaries.in` | Case-insensitive syntax, commas, two-digit registers, address 252 | F30=4.5; F29=3.25; Mem[252]=4.5 |
| `address18.in` | Assignment-style effective byte address R1+8=18 | F4=16777216; F1=30.1; Mem[32]=16777216 |
| `binary32_transfer.in` | Single-precision initialization, storage and forwarding | F3=F5=16777216; original F1=16777217; Add.d F4=16777218 |
| `byte_overlap.in` | Two four-byte stores begin at 18 and 20 | Final F3=0; F4=2; F5=2 |
| `partial_overlap_replay.in` | Newer store masks only two bytes of an unresolved older store | Replay occurs; F3=2.003875732421875 |

The sample report's timing outputs are not golden results: that implementation also
widens writeback and commit and changes memory concurrency. These tests keep the
assignment's single CDB and single memory port and use one commit per cycle.

The starter's `Bne R1 R0 -12` used a byte displacement in the old implementation.
Its exact word-offset equivalent is `-3`, which loops over only the pointer-update
instructions. The separate DAXPY workload explicitly changes the branch target to
`-8` words to run the full loop. Neither transformation is concealed.


The byte-memory regression module checks every end-of-memory start from 249 through
252, rejects start 253 and above, and verifies the requested effective address 18.
Loads and stores transfer four little-endian IEEE binary32 bytes. The `.d` ALU
instructions retain Python floating-point arithmetic; they are not rounded to
binary32. Tests cover exact 16777217-to-16777216 transfer rounding, direct and
partially merged forwarding, selected pending store data, byte-specific replay,
signed zero, subnormals, underflow and overflow. Nonfinite values are serialized in
strict CLI JSON as the strings `NaN`, `Infinity` and `-Infinity`.

`results/memory_fix_regression_check.txt` records the comparison against outputs
captured before the memory correction: all original 48 runs preserve their final
registers, memory, cycle totals and every pre-existing instruction-stage field.
The eight sample-report runs remain 36/36/36/36 and 47/46/46/46 cycles.
