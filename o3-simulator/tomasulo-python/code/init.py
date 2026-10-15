"""Parse the assignment's case-insensitive hardware/assembly input format."""
import math
import re
from pathlib import Path

from model import Config, Instruction, Program, UnitConfig


def register(token, kind=None):
    token = token.upper()
    if not re.fullmatch(r"[RF](?:[0-9]|[12][0-9]|3[01])", token):
        raise ValueError(f"Invalid register: {token}")
    if kind and not token.startswith(kind):
        raise ValueError(f"Expected a {kind} register, got {token}")
    return token


def address_valid(address):
    return isinstance(address, int) and 0 <= address <= 252 and address % 4 == 0


def parse_instruction(line):
    tokens = line.replace(",", " ").split()
    op = tokens[0].lower()
    if op in ("ld", "sd") and len(tokens) == 3:
        fp = register(tokens[1], "F")
        match = re.fullmatch(r"([+-]?\d+)\((R\d+)\)", tokens[2], re.I)
        if not match:
            raise ValueError("Expected offset(Rn) for a memory operand")
        offset, base = int(match[1]), register(match[2], "R")
        return Instruction(op, line, fp if op == "ld" else None,
                           (base,) if op == "ld" else (base, fp), offset)
    if op in ("beq", "bne") and len(tokens) == 4:
        return Instruction(op, line, sources=(register(tokens[1], "R"),
                           register(tokens[2], "R")), immediate=int(tokens[3]))
    if op == "addi" and len(tokens) == 4:
        return Instruction(op, line, register(tokens[1], "R"),
                           (register(tokens[2], "R"),), int(tokens[3]))
    if op in ("add", "sub", "add.d", "sub.d", "mult.d") and len(tokens) == 4:
        kind = "F" if "." in op else "R"
        return Instruction(op, line, register(tokens[1], kind),
                           (register(tokens[2], kind), register(tokens[3], kind)))
    raise ValueError(f"Unsupported or malformed instruction: {line}")


def parse_text(text):
    config = Config()
    registers = {f"{kind}{i}": 0 if kind == "R" else 0.0
                 for kind in ("R", "F") for i in range(32)}
    memory = {i: 0.0 for i in range(0, 256, 4)}
    instructions = []
    labels = {"integer adder": "integer", "fp adder": "fp_add",
              "fp multiplier": "fp_mul", "load/store unit": "address"}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].split("//", 1)[0].strip()
        if not line:
            continue
        try:
            hardware = re.fullmatch(
                r"(Integer adder|FP adder|FP multiplier|Load/store unit)\s+(.+)", line, re.I)
            if hardware:
                unit = labels[hardware[1].lower()]
                values = [int(x) for x in hardware[2].split()]
                if len(values) != (4 if unit == "address" else 3):
                    raise ValueError("Hardware row has the wrong number of columns")
                setattr(config, unit, UnitConfig(values[0], values[1], values[-1]))
                if unit == "address":
                    config.memory_latency = values[2]
                continue
            setting = re.fullmatch(r"(ROB entries|Issue width)\s*=\s*([+-]?\d+)", line, re.I)
            if setting:
                setattr(config, "rob_entries" if setting[1].lower() == "rob entries"
                        else "issue_width", int(setting[2]))
                continue
            if "=" in line:
                for item in line.split(","):
                    match = re.fullmatch(r"\s*(Mem\[([+-]?\d+)\]|[RF]\d+)\s*=\s*(\S+)\s*", item, re.I)
                    if not match:
                        raise ValueError(f"Malformed initialization: {item}")
                    if match[2] is not None:
                        address = int(match[2])
                        if not address_valid(address):
                            raise ValueError("Memory addresses must be aligned bytes in 0..252")
                        value = float(match[3])
                        memory[address] = value
                    else:
                        name = register(match[1])
                        value = int(match[3]) if name[0] == "R" else float(match[3])
                        if name == "R0" and value != 0:
                            raise ValueError("R0 is hardwired to zero")
                        registers[name] = value
                    if isinstance(value, float) and not math.isfinite(value):
                        raise ValueError("Initial values must be finite")
                continue
            instructions.append(parse_instruction(line))
        except ValueError as error:
            raise ValueError(f"Line {number}: {error}") from error
    config.validate()
    for pc, instruction in enumerate(instructions):
        if instruction.branch and not 0 <= pc + 1 + instruction.immediate <= len(instructions):
            raise ValueError(f"Branch at byte PC {4 * pc} targets outside the program")
    return Program(config, instructions, registers, memory)


def read_program(path):
    return parse_text(Path(path).read_text(encoding="utf-8"))
