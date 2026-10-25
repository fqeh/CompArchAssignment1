# Tomasulo Algorithm Implementation

**Assignment author: Ali Alfageeh**

This Python implementation supports in-order issue widths 1, 2, 3, and 4,
out-of-order execution, register renaming, speculative branches, a reorder
buffer, and speculative load/store ordering with recovery. The code uses only
the Python standard library and requires Python 3.10 or later.

## Run

From the extracted submission directory:

```bash
python3 code/main.py
python3 code/main.py tests/benchmarks/sample_01.in --issue-width 4
python3 code/main.py tests/benchmarks/sample_02.in --issue-width 2 --json result.json
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tests/run_benchmarks.py
```

The first command uses `code/code.in`, a small loop whose input explicitly sets
issue width to 2. If the input omits `Issue width`, the simulator defaults to 1.
`--issue-width` overrides the input. The maximum cycle count defaults to 100000;
use `--max-cycles N` to change it. Errors produce a nonzero exit status.

The result includes the ISSUE, EX, MEM, WB, and COMMIT cycles for every dynamic
instruction, all 64 architectural registers, nonzero memory locations, and
statistics. Squashed instructions are retained and labeled; they never commit.
The optional JSON includes the same values, each dynamic instruction's ID, and
`memory_bytes`, the complete 256-byte memory image. The readable memory table
shows nonzero binary32 views at aligned word starts and at any explicitly
initialized or committed-store start address. These views can overlap; the byte
image is authoritative.
Nonfinite values are emitted as the strings `NaN`, `Infinity`, or `-Infinity`
in JSON, keeping the file valid JSON. Raw bytes preserve the actual memory bits.

## Input

```text
# Unit          RS  EX  MEM  FUs
Integer adder    4   1        1
FP adder         4   3        1
FP multiplier    4   5        1
Load/store unit  4   1   6    1
ROB entries = 64
Issue width = 4
R1=12, R2=32, F20=3.0
Mem[12]=1.0
Ld F1, 0(R1)
Mult.d F2, F1, F20
```

Register names and opcodes are case insensitive. Commas between operands are
optional. Supported instructions: `Ld`, `Sd`, `Beq`, `Bne`, `Add`, `Sub`,
`Addi`, `Add.d`, `Sub.d`, and `Mult.d`. Registers initialize to zero unless
specified; R0 remains zero. Memory contains 256 shared bytes. Each load or store
accesses four bytes beginning at any integer address from 0 through 252,
including unaligned address 18. Starts below 0 or above 252 fail when the access
reaches the head of the ROB; a squashed wrong-path access is harmless.

`Mem[address]=value`, stores, loads, and store-to-load forwarding use IEEE-754
binary32 memory values in little-endian byte order. Stores round to nearest,
ties to even; finite overflow becomes signed infinity. Register initialization
and `.d` arithmetic retain Python floating-point precision. For example,
storing and reloading register value 16777217 yields 16777216. The assignment
does not specify endianness or an extra unaligned-access penalty: little-endian
storage and the configured memory latency for all starts are explicit model
conventions. Overlapping accesses observe the same underlying bytes.

## Architecture and cycle conventions

- Only ISSUE width changes. One CDB broadcasts at most one result per cycle;
  one ROB entry commits per cycle. Commit remains in order.
- Instructions issue in program order, stopping at the first full ROB, RS, or
  load/store queue. Source tags are captured before destination renaming.
- Ready instructions execute out of order. Integer and address units are
  unpipelined; each FP unit can initiate one instruction per cycle.
- Stages are visited in the order COMMIT, WB, MEM, EX, ISSUE. Readiness timestamps
  prevent a result broadcast this cycle from being consumed by EX this cycle.
  A one-cycle Addi can have ISSUE=1, EX=2, WB=3, COMMIT=4.
- EX and MEM ranges are inclusive. RS entries are released at dispatch to EX.
  Load/store queue entries remain through load completion or store commit.
- Multiple load/store FUs mean multiple address units. Memory remains a single
  serialized, nonpipelined port. Fully forwarded loads also use this path for
  one cycle; partial forwarding merged with memory uses the configured latency.
- Stores start their memory operation only at the ROB head, retain the port for
  the configured memory latency, and update memory/commit on the final cycle.
  Store MEM timing therefore represents the commit-time memory access. Stores
  and branches do not use CDB write-back; their WB column is `-`.
- For each load byte, forwarding selects the youngest older store covering that
  byte. If any contributing store data is not ready, the load waits. Store data
  is rounded/encoded to binary32 before forwarding. A load may speculate past
  an unresolved store address. If it later overlaps bytes supplied from an
  older source, the earliest violating load and younger work are squashed and
  reissued. Per-byte source metadata remains in the ROB for this check.
- The predictor uses an initially empty, direct-mapped eight-entry BTB with PC
  tags, one direction bit, and a target. The index is `(byte_PC >> 2) & 7`.
  A miss predicts not taken. The bit/target update at branch resolution.
- A misprediction resolved in cycle n squashes younger work, rebuilds the RAT
  from surviving ROB entries, and resumes correct issue in n+2. The same
  recovery delay is used for a memory-order replay. Predictions can redirect
  later issue slots in the same cycle; retired architectural state is precise.

## Starter and sample-report differences

The original starter is preserved unchanged under `original/tomasulo-python/`
and its ZIP is also included. The starter was written by Qing (2017).

This is a substantial refactor, not just an issue-loop patch: the starter has
hardcoded configuration/state, no branch prediction, fragile mutable state,
and incorrect memory/renaming behavior. The stage modules remain recognizable;
`code/simulator.py` centralizes state and recovery. `changes.patch` records
the complete source differences, including the new simulator module.

The supplied sample PDF is used as a report-format reference. Its additional
multiple-WB/multiple-commit behavior and branch limitations are not copied.
Actual measured timings consequently differ. The two sample workloads are
transcribed as test inputs; none of their printed timing results are reused.

**Branch offsets:** the assignment specifies word offsets:
`byte_target = byte_PC + 4 + 4 * offset`. Internally the PC is a word index.
The starter instead divides offsets by four. To run its unchanged input:

```bash
python3 code/main.py original/tomasulo-python/code/test_case.txt --legacy-branch-bytes
```

The starter's `Bne R1 R0 -12` corresponds to word offset -3, looping only over
the two pointer updates and branch. `starter_equivalent.in` preserves that
behavior using -3. `daxpy_loop.in` separately uses -8 to loop the full body.
The illustrative PDF input computes address 18; this revision accepts it.
The finite address-18 regression isolates the load because the sample's branch
would otherwise loop indefinitely without changing its condition.

## Files and reproduction

- `Tomasulo_Assignment_Report_Ali_Alfageeh.pdf`: report with before/after code
  snapshots, measured timing tables for widths 1-4, validation and limitations.
- `code/`: completed runnable simulator.
- `tests/`: regression tests, independent sequential interpreter and benchmarks.
- `results/`: full text/JSON traces for every benchmark at all four widths and
  summary CSV/JSON.
- `report_assets/`: source-code snapshot PNGs and manifest with source hashes.
- `tools/`: report-building source. Requires `reportlab` and `Pillow` separately;
  these are not required to run the simulator or its tests.
- `original/`: unchanged starter and supplied assignment/sample PDFs.
- `revision_before/`: selected files from the previous implementation,
  retained solely as before snapshots for the memory compatibility corrections.
- `changes.patch`: before/after source diff.

To regenerate the report in the provided environment:

```bash
python3 tests/run_benchmarks.py
python3 tools/build_report.py
```

The report builder uses DejaVu fonts from `/usr/share/fonts/truetype/dejavu`.
On another operating system, set the `FONT_DIR` environment variable to an
installed DejaVu font directory. The submitted PDF does not need those dependencies.

## Model limits

This is an instructional scheduling model, not a full ISA emulator. Loads and
stores use binary32, while `.d` arithmetic and FP register initialization use
Python precision; floating-point rounding-mode control and status flags are not
modeled. Integer arithmetic does not model fixed-width overflow. It does not model
caches, an OS, interrupts, or precise exception-handler execution. Invalid
committing accesses stop with an error. Termination occurs when the PC is
outside the program and the ROB is empty. The documented test suite reports
no known unresolved functional failure in the tested instruction set.

Repository: [Computer Architecture Assignment 1](https://github.com/fqeh/CompArchAssignment1).
