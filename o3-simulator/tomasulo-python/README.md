# Tomasulo simulator: in-order issue width 1-4

This implementation extends and repairs the provided Python Tomasulo simulator.
It supports out-of-order execution, register renaming, in-order commit,
loads/stores, a one-bit branch predictor with an eight-entry BTB, and memory
ordering replay. The simulator implementation is in `code/`.

## Requirements and quick start

Python 3.10 or newer. No third-party packages are required.
Run these commands from `o3-simulator/tomasulo-python`:

```sh
python3 code/main.py
python3 code/main.py benchmarks/sample_case_01.in --issue-width 4
python3 code/main.py benchmarks/array_loop.in --issue-width 2 --json results/my_run.json
python3 -m unittest discover -s tests -v
python3 run_benchmarks.py
```

`python3 code/main.py` reads `code/code.in` regardless of the current directory.
The optional `--issue-width` overrides the input setting. `--max-cycles` defaults
to 100000 and stops nonterminating programs with an error. The output directory
for an explicitly requested JSON file must already exist.

## Input

Instructions are case-insensitive; commas between operands are optional.
Blank lines and `#` comments are accepted. An instruction-only input uses the
default configuration below. A complete input may contain:

```text
# Unit              RS  EX  MEM  FUs
Integer adder        2   1        1
FP adder             3   3        1
FP multiplier        2  20        1
Load/store unit      3   1   4    1
ROB entries = 128
Issue width = 2
R1=4, R2=8, F2=3.0
Mem[4]=1.0, Mem[8]=2.0
Ld F4 0(R1)
Add.d F6 F4 F2
Sd F6 0(R2)
```

All configuration numbers must be positive integers. Issue width is 1-4 and
defaults to 1. All registers and memory words initially contain zero unless
initialized. Duplicate settings, invalid registers, and malformed instructions
produce errors. R0 is permanently zero; writes to it are discarded.

Supported ISA: `Ld`, `Sd`, `Beq`, `Bne`, `Add`, `Sub`, `Addi`, `Add.d`, `Sub.d`,
and `Mult.d`. R0-R31 are integer registers; F0-F31 and memory words hold
IEEE 754 binary32 (32-bit single-precision) values. FP input values and every
`Add.d`, `Sub.d`, and `Mult.d` result are rounded to binary32, as are loads,
stores, and forwarded values. Rounding uses nearest, with ties to even.
Initial values must be finite in binary32. Arithmetic overflow produces signed
infinity; underflow supports subnormal values and signed zero. Python floats
are used as containers for the rounded values. Console output uses up to nine
significant digits to distinguish binary32 values.

Memory contains 64 words at byte addresses 0, 4, ..., 252. Word accesses must be
aligned and within this range. Branch displacements are signed **word offsets**:
`target_byte_PC = PC + 4 + (offset << 2)`. Internally this is
`target_instruction_index = index + 1 + offset`. A target immediately after the
last instruction is a valid program exit.

The default array example uses `Bne R1 R0 -8` to return from instruction 8 to
instruction 1, following the assignment's word-offset rule.

## Timing and hardware conventions

- Cycles start at 1. A newly issued instruction can begin EX in the next cycle.
- Issue processes up to the configured width in program order. A full ROB or
  required RS/LSQ stops that cycle's issue bundle. Each successful issue updates
  renaming before the next instruction is considered.
- Ready instructions are selected by dynamic age within each FU class. Integer
  and address units are unpipelined. Each FP unit can accept one new operation
  per cycle. The RS is released when execution begins; the executing operation
  occupies its FU/pipeline instead.
- The load/store row's FU count configures dedicated address-generation units.
  Data memory remains **one non-pipelined port** regardless of that count.
- EX and MEM intervals are inclusive: end = start + configured latency - 1.
- One common data bus broadcasts at most one result per cycle. Results become
  eligible for WB the cycle after completion; consumers start EX no earlier
  than the cycle after WB. Completion time, then dynamic age, breaks CDB ties.
- Commit width is fixed at one. The assignment specifies widening issue, but
  does not specify widening commit. A non-store commits no earlier than the
  cycle after it becomes ready. Branches have EX and COMMIT, with no MEM/WB.
- Stores access memory only at the ROB head. Their commit stage spans the memory
  latency; memory changes and the ROB entry retires at its end. Store MEM and
  COMMIT intervals therefore overlap. A store has no CDB write-back.
- A load forwards from the youngest older matching store in one cycle when its
  data is ready. There is at most one forwarding transfer per cycle; forwarding
  does not occupy the data-memory port. Loads leave the LSQ after obtaining data;
  stores remain until commit completes.
- Loads may speculatively access memory while older store addresses are unknown.
  When a store address resolves, an incorrectly ordered younger load and all
  younger instructions are squashed and re-fetched. Completed loads remain
  tracked in the ROB for this check even after leaving the LSQ.
- The direct-mapped BTB has eight entries indexed by `(byte_PC >> 2) & 7` and
  tagged with the full PC. Each resident entry has one direction bit; a miss
  predicts not-taken. Resolution updates the entry in EX. A branch miss detected
  at cycle n suppresses issue in n and n+1; correct issue resumes in n+2.
  Memory replay uses the same recovery delay.
- Recovery removes younger ROB/RS/LSQ entries, active execution, memory reads,
  and pending results. RAT mappings are reconstructed from surviving entries.
- Invalid speculative memory accesses are recorded as faults and reported only
  if they reach the ROB head; discarded wrong-path accesses do not raise errors.
- Stage functions run commit, WB, EX, MEM, then issue. Timestamp checks enforce
  the timing boundaries above; resources released earlier in a cycle can be
  reused by issue in that same cycle.

## Output and validation

The console report lists each dynamic instruction (including loop iterations),
its byte PC, ISSUE/EX/MEM/WB/COMMIT cycles, and whether it committed or was
squashed. Blank stages do not apply or were not reached. It then prints all 64
registers, nonzero memory words, and counters. JSON preserves the full trace.

`run_benchmarks.py` first runs the unittest suite, then validates every benchmark
at widths 1-4 against an independent sequential interpreter in
`tests/reference.py`. It compares all registers, nonzero memory, and the exact
committed PC sequence. Behavioral tests also check timing, resource limits,
forwarding, replay, predictor aliasing, precise faults, and hand-calculated
values for both sample-report programs. Ninety deterministic generated programs
supply 360 additional width comparisons.

Results are saved in `results/`: one text/JSON trace per run, `summary.csv`,
`summary.json`, and `tests.txt`. `summary.json` includes source/input hashes.

## Scope and limitations

This is an educational numeric timing model, not a bit-exact processor emulator.
Floating-point values are rounded to binary32. Python integers are unbounded;
fixed-width integer overflow, FP exception flags/traps, caches, and hardware
exception handlers are not modeled. Memory is modeled as 64 numeric words,
not raw bytes.
The assignment's illustrative `R1=10; Ld F4,8(R1)` would address unaligned byte
18; this implementation enforces the documented 64-word memory organization.

The sample PDF guides the report structure. Its widened WB/commit and in-order
execution are not copied: this simulator retains one CDB, single commit, and
Tomasulo out-of-order execution. Its cycle counts are therefore not expected to
match the sample PDF. The two sample input programs are included verbatim in
`benchmarks/sample_case_01.in` and `sample_case_02.in` apart from comments and the
explicit issue-width setting.

## File map

| File | Responsibility |
|---|---|
| `code/init.py` | Configuration, records, ISA/input validation |
| `code/issue.py` | In-order issue and register renaming |
| `code/exe.py` | Functional units, addresses, branch resolution |
| `code/mem.py` | Memory port and store-to-load forwarding |
| `code/wb.py` | Single CDB and operand wake-up |
| `code/commit.py` | In-order retirement and store commit |
| `code/simulator.py` | Cycle driver, BTB, squash/replay, results |
| `code/print_status.py` | Human-readable timing and state output |
| `code/main.py` | Command-line interface |
| `tests/` | Behavioral tests and independent ISA interpreter |
| `benchmarks/` | Twelve reproducible input programs |

The local submission materials are ready to be added to a GitHub repository;
no repository initialization or publication is performed by these scripts.
