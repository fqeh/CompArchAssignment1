# Tomasulo Algorithm Implementation

**Ali Alfageeh**

I extended the simulator to support issue widths 1 through 4, out-of-order
execution, register renaming, branch prediction and recovery, and speculative
load/store ordering. The model uses one common data bus and one in-order commit
per cycle.

[Assignment report](Tomasulo_Assignment_Report_Ali_Alfageeh.pdf) ·
[GitHub repository](https://github.com/fqeh/CompArchAssignment1)

## Run

Requires Python 3.10 or later and only the Python standard library.
From the repository root:

```bash
cd tomasulo
python3 code/main.py
python3 code/main.py inputs/sample_01.in --issue-width 4
python3 code/main.py inputs/sample_02.in --issue-width 2 --json result.json
```

The default input is `code/code.in`, which sets issue width to 2. An input that
omits `Issue width` defaults to 1. `--issue-width` accepts 1, 2, 3, or 4 and
overrides the input setting. Use `--max-cycles N` to change the default limit
of 100000 cycles.

Output includes each instruction's ISSUE, EX, MEM, WB, and COMMIT timing,
final registers and memory, and execution statistics. Squashed instructions
are labeled in the output. `--json` also writes the complete result to a file.

## Files

- `code/`: nine Python modules and the default program, `code.in`.
- `inputs/`: the two sample programs used in the report's timing tables.
- `Tomasulo_Assignment_Report_Ali_Alfageeh.pdf`: assignment description,
  code changes, measured results, and model limitations.

## Input and model conventions

An input defines reservation-station counts, execution and memory latencies,
functional-unit counts, ROB size, issue width, initial values, and instructions.
The included inputs show the format.

Supported instructions are `Ld`, `Sd`, `Beq`, `Bne`, `Add`, `Sub`, `Addi`,
`Add.d`, `Sub.d`, and `Mult.d`. Register names and opcodes are case insensitive.
R0 stays zero. Branch offsets are measured in words; use
`--legacy-branch-bytes` for older input files with byte offsets.

Memory contains 256 shared bytes. Loads and stores transfer four little-endian
IEEE-754 binary32 bytes at any start address from 0 through 252, including
unaligned addresses. Floating-point register initialization and arithmetic
retain Python floating-point precision. Memory uses one serialized port.

For the included report examples, the cycle counts at issue widths 1, 2, 3,
and 4 are 36/36/36/36 for Sample 01 and 47/46/46/46 for Sample 02.
