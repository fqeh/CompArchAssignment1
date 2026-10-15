# Multi-issue Tomasulo implementation report

## 1. Objective and changes to the supplied code

The simulator accepts issue widths from one through four while preserving
in-order issue, out-of-order execution and in-order architectural retirement.
The implementation uses Python's standard library and keeps the starter's five
stage modules. The supplied starter credited Qing (May 2017) and provided the
basic ROB, RAT, reservation-station and load/store-queue organization.

The changes extend beyond wrapping issue in a loop because several starter
assumptions would otherwise make multiple issue incorrect:

| File | Change and purpose |
| --- | --- |
| `init.py` | Parses hardware, issue width, initial state and the entire case-insensitive ISA from one file. Reports invalid inputs with line numbers. |
| `model.py` | Adds real dataclass instances for instructions, operands and pipeline entries, replacing mutable attributes on namedtuple classes. |
| `issue.py` | Issues up to the configured width in program order. Stops the entire bundle at the first full RS, LSQ or ROB. Captures sources before updating the RAT for each destination. |
| `exe.py` | Schedules the oldest ready work independently per unit, counts each execution cycle once, respects configured FU counts, and resolves branches. |
| `mem.py` | Uses one nonpipelined memory port, finds the youngest matching older store across the entire LSQ, and forwards in one cycle. |
| `wb.py` | Broadcasts at most one completed value per cycle, waking only consumers with the matching unique tag. An older completion cannot overwrite a newer RAT mapping. |
| `commit.py` | Commits the ROB head only. Registers change at retirement and stores change memory only while committing at the head. R0 remains zero. |
| `simulator.py` | Owns processor state, steps the stages, restores the RAT and removes younger work after branch mispredictions or memory-order violations. |
| `main.py`, `print_status.py` | Add the CLI, complete timing table, architectural register/memory output and optional JSON/file output. |

Source values in a multi-issue bundle see earlier renames from that same bundle.
For example, issuing `Addi R1 R0 7` and `Add R2 R1 R1` together makes both R2
operands wait for the first instruction. Capturing source operands before the
destination rename also handles self-updates and avoids WAR hazards. Monotonic
dynamic tags prevent stale results from matching reused ROB positions.

## 2. Hardware and timing conventions

The input controls RS/LSQ capacities, ROB entries, FU counts, execution latencies,
memory latency and issue width. Integer and address units are unpipelined. Each
FP unit can accept one new operation per cycle. Increasing the load/store FU
count adds address calculators; it does not add memory ports.

The assignment specifies **one CDB**. This implementation therefore keeps one
writeback and at most one retirement per cycle at every issue width. The sample
report increased these widths too and allowed multiple memory accesses. Its
cycle totals are illustrative, not a cycle-accurate oracle for the assignment's
single-CDB, single-port configuration. Execution remains out of order.

The simulator calls COMMIT, WB, MEM, EX, ISSUE in each cycle and checks timestamps
at stage boundaries. An instruction cannot execute during its issue cycle;
consumers cannot execute during their producer's WB cycle. EX and MEM intervals
are inclusive. An operation completing in cycle n can broadcast in n+1 and
retire in n+2, unless an older instruction or CDB contention delays it.

Stores calculate their address independently of store-data availability. A
store starts its memory transfer only when it is at the ROB head and its data
is ready. The transfer occupies the memory port for the configured latency;
its last cycle writes memory and is also its COMMIT cycle. The MEM column shows
that transfer interval. Stores and branches do not use the CDB.

### Branch prediction and recovery

An eight-entry tagged, direct-mapped BTB uses `(byte_PC >> 2) & 7`. Entries hold a
one-bit taken/not-taken outcome and a target. Missing entries predict not taken.
Prediction selects the next instruction during issue, including within a bundle.
Both Beq and Bne execute on integer units. On a misprediction, the processor
removes younger ROB/RS/LSQ/executing/memory entries and rebuilds the RAT from
surviving writers. Correct fetch starts at resolution cycle n+2. Architectural
registers need no rollback because wrong-path instructions cannot retire before
the unresolved branch. Wrong-path stores cannot change memory.

### Memory disambiguation

Loads forward from the youngest older store with a matching known address,
waiting if that store's data is unavailable. A nonmatching store between that
store and the load does not prevent forwarding. Loads may access memory past
older stores whose addresses are still unknown, as described in the assignment.

When an older store's address resolves, it checks younger loads still in the
ROB, including loads already removed from the LSQ. An alias causes the earliest
conflicting load and all younger instructions to be squashed and reissued.
This avoids committing stale speculative data. The replay uses the same n+2
restart convention. The policy can conservatively replay a load even when an
intervening store would shield it; this affects timing, not program results.
Forwarding consumes the modeled memory-stage port for one cycle.

### Input corrections and numeric conventions

Branch offsets follow the assignment ISA: `PC + 4 + (offset << 2)` in byte
addresses. The starter's `Bne R1 R0 -12` used a legacy byte-offset convention;
interpreting it literally as the assignment's word offset would jump outside
the program. The bundled vector example now uses `-8`, returning to its first
instruction and applying the complete load/multiply/add/store loop three times.
This intentional benchmark correction is present in both `code.in` and
`test_case.txt`. Both files now include the complete original hardware and
initial-state configuration; the default runnable example is `test_case.txt`.

Memory consists of 64 aligned words at byte addresses 0 through 252. Unaligned
or out-of-range dynamic accesses raise a precise error at retirement; wrong-path
faults can be squashed. The PDF's short format example uses R1=10 and 8(R1),
which is unaligned under this word-memory interpretation. Use an aligned base
when turning that illustrative input into an executable benchmark.

## 3. Correctness testing

Run:

```sh
python3 -m unittest discover -s tests -v
python3 run_benchmarks.py
```

The unittest suite checks manually calculated timing, same-bundle dependencies,
RAW/WAR/WAW behavior, R0, blocked issue bundles, a one-entry ROB/LSQ, pipelined and
unpipelined units, FU counts, out-of-order execution, CDB contention, forwarding,
store-data dependencies, unresolved-store replay, nonaliasing speculation,
single-port serialization, wrong-path store suppression, RAT recovery, branch
loops, BTB collisions, precise faults, parser validation and the CLI.

A separate sequential interpreter implements the ISA without any timing,
renaming or prediction state. All benchmark runs and 40 seeded random programs
at each width (160 randomized runs) must match its entire architectural state
and committed PC sequence. Random tests vary hardware capacities, latencies,
FU counts and ROB size, with arithmetic, memory operations and forward branches.
Targeted tests cover backward loops and unresolved store addresses. Timing
checks also verify stage separation, configured latency, single writeback and
in-order single retirement.

### Benchmarks and expected final results

Every benchmark is run at widths 1, 2, 3 and 4. The expected results below are
identical across all widths; complete architectural states are saved in
[`results/final_states.json`](results/final_states.json).

| Benchmark | Purpose | Selected final results |
| --- | --- | --- |
| `branches` | Loop prediction, taken/not-taken recovery, wrong-path store | R2=4, R3=8; memory stays zero |
| `dependencies` | Same-destination writers, captured sources, R0 | F3=4, F4=7, R1=5, R2=16, R3=21, R0=0 |
| `independent` | Independent integer and FP work; retirement bottleneck | F3=6, F7=9, F10=6, R4=4 |
| `late_critical_path` | Wider issue starts a late multiply/add chain earlier | R1..R8=1..8, F3=6, F4=12 |
| `memory` | Unknown-store replay and forwarding across another store | F3=9, F4=18, F5=7; Mem[0]=9, Mem[4]=7, Mem[8]=9 |
| `sample_report_01` | First supplied sample-report instruction stream | R1=28, F1=5, F2=25, F4=26 |
| `sample_report_02` | Second supplied stream, including multiple FUs | R1=24, F1=6, F2=36, F4=37 |
| `structural` | Two-entry ROB, one-entry queues and long latencies | F5=8, F6=8, F7=16; Mem[0]=8 |
| `vector_loop` | Full three-iteration memory/arithmetic loop | R1=0, R2=20, F20=6; Mem[24]=15, Mem[28]=11, Mem[32]=7 |

## 4. Measured results by issue width

These are measured simulator cycles, not wall-clock runtime. Speedup is
width-1 cycles divided by width-4 cycles. The benchmark runner regenerates this
table directly from verified executions.

<!-- RESULTS START -->

| Benchmark | Width 1 | Width 2 | Width 3 | Width 4 | Speedup (1/4) |
| --- | ---: | ---: | ---: | ---: | ---: |
| branches | 25 | 20 | 20 | 20 | 1.25x |
| dependencies | 20 | 20 | 20 | 20 | 1.00x |
| independent | 20 | 20 | 20 | 20 | 1.00x |
| late_critical_path | 27 | 23 | 21 | 21 | 1.29x |
| memory | 42 | 41 | 40 | 40 | 1.05x |
| sample_report_01 | 36 | 36 | 36 | 36 | 1.00x |
| sample_report_02 | 47 | 46 | 46 | 46 | 1.02x |
| structural | 40 | 40 | 40 | 40 | 1.00x |
| vector_loop | 66 | 65 | 65 | 65 | 1.02x |

<!-- RESULTS END -->

The late critical path benefits because a wider front end reaches its multiply
sooner. The branch benchmark also benefits. The independent benchmark has
sufficient early work to keep single retirement busy after the first long
multiply finishes, so issuing it earlier does not reduce the final cycle count.
The dependency and small-queue cases similarly retain their critical bottlenecks.
Wider issue alone does not guarantee proportional speedup with one CDB, one
retirement slot and one memory port.

All 36 full instruction timing tables and final register/memory dumps are in
[`results/`](results/). For example, compare
[`vector_loop_w1.txt`](results/vector_loop_w1.txt) with
[`vector_loop_w4.txt`](results/vector_loop_w4.txt), or
[`late_critical_path_w1.txt`](results/late_critical_path_w1.txt) with
[`late_critical_path_w4.txt`](results/late_critical_path_w4.txt).
[`summary.csv`](results/summary.csv) includes cycle counts, committed instruction
counts, branch mispredictions and memory replays for every run. Squashed dynamic
instructions remain in traces and are explicitly marked; they never receive a
COMMIT cycle.

## 5. What works and limitations

All required opcodes, issue widths 1–4, input/output features, configurable
hardware, register hazards, branch prediction/recovery, memory forwarding and
speculative-load replay are implemented. The tests described above pass.
No known failing tested behavior remains.

This is a timing/ordering simulator, not a bit-exact MIPS implementation. Like
the starter, it uses Python floating-point arithmetic and unbounded integers;
it does not emulate IEEE-754 single-precision rounding, integer overflow,
caches, virtual memory, interrupts or general exception handlers. Invalid
memory accesses are reported rather than delivered to a handler. Predictor
updates occur at EX and are not rolled back when an older branch later squashes
a resolved branch; this can affect future predictions but not architectural
correctness. Fetch/decode has no additional width or alignment restrictions
beyond issue width. The complete dynamic history is retained, so very long
simulations use memory proportional to the number of issued instructions.

The supplied sample report's unsupported-branch limitation and multi-CDB model
are not inherited. Its PDFs are retained for context and are not authored as
part of this implementation.
