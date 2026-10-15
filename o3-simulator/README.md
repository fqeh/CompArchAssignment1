# Multi-issue Tomasulo simulator

Computer Architecture assignment: a Python simulator with **in-order issue widths
1–4**, register renaming, out-of-order execution, in-order retirement, branch
prediction/recovery, and memory disambiguation.

Requires **Python 3.9 or newer**. No third-party dependencies or build step.

## Run

From this repository's root:

```sh
python3 tomasulo-python/code/main.py
python3 tomasulo-python/code/main.py benchmarks/vector_loop.txt --issue-width 4
python3 tomasulo-python/code/main.py benchmarks/branches.txt --issue-width 2 --json
python3 tomasulo-python/code/main.py benchmarks/memory.txt --output memory-output.txt
```

The input file can contain `Issue width = 1`, `2`, `3`, or `4`. The default is 1;
`--issue-width` overrides the input setting. `--max-cycles` defaults to 100000 and
stops nonterminating programs with a clear error.

Output includes every dynamic instruction's ISSUE, EX, MEM, WB and COMMIT cycles,
explicitly marked squashed instructions, all 64 registers, and nonzero memory.
EX/MEM ranges include both endpoints. PCs and memory addresses are in bytes.

## Input

```text
# Unit             RS  EX  MEM  FUs
Integer adder       4   1        1
FP adder            3   3        1
FP multiplier       2  20        1
Load/store unit     3   1   4    1
ROB entries = 128
Issue width = 2
R1=4, F2=3.0
Mem[4]=2.0
Ld F1, 0(R1)
Mult.d F3, F1, F2
Sd F3, 4(R1)
```

Instructions, register names, and configuration names are case insensitive.
Commas between instruction operands are optional; initialization assignments are
comma-separated. Blank lines, `#` comments and `//` comments are accepted.
Omitted hardware settings use the defaults shown in `model.py`; omitted register
and memory values are zero. R0 always reads zero.

Supported ISA: `Ld`, `Sd`, `Beq`, `Bne`, `Add`, `Sub`, `Addi`, `Add.d`, `Sub.d`,
`Mult.d`. Memory is 256 bytes / 64 words: aligned byte addresses 0, 4, …, 252.
Branch immediates are **signed word offsets**:
`target_byte_PC = PC + 4 + (offset * 4)`. The bundled vector loop uses `-8`
to return from its eighth instruction to its first. See the report for the
correction to the starter's legacy byte-offset example.

The integer and address units are unpipelined; FP add and multiply units are
pipelined. FU counts are configurable. Additional load/store units add address
calculators, while memory remains single-ported and unpipelined. There is one
CDB and a one-instruction retirement limit, independent of issue width.

## Verify and reproduce the report

```sh
python3 -m unittest discover -s tests -v
python3 run_benchmarks.py
```

The suite includes manually checked timings, hazard/recovery tests, all benchmark
widths, and 40 deterministic randomized programs at each of the four widths.
A separate sequential interpreter checks registers, memory and the committed
instruction path. The benchmark runner regenerates all traces and measured
results, including the results table in the report.

- [Report](REPORT.md): implementation, timing conventions, results, limitations.
- [Benchmarks](benchmarks/): nine programs, including both sample-report cases.
- [Saved results](results/): 36 complete traces, summary CSV and final states.
- [Source](tomasulo-python/code/): the original stage organization with revised internals.
- [Assignment](programming-tomasulo.pdf) and [sample report](Sample_Tomasulo_Assignment_Report.pdf).

## Starter attribution

This work starts from the supplied `tomasulo-python` simulator. Its original
source comments credit **Qing, May 2017**. The ISSUE / EX / MEM / WB / COMMIT
module organization is retained; the state model and stage implementations have
been reworked to make multi-issue dependencies, precise retirement and recovery
consistent. No authorship claim is made for the supplied starter or PDFs.
