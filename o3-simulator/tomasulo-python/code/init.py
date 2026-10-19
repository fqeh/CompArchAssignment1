"""Input parsing and records. Based on Qing's (2017) Tomasulo simulator.

Internal PCs are instruction indices; memory addresses are byte addresses.
"""
from dataclasses import dataclass
import math
from pathlib import Path
import re
import struct


@dataclass
class Config:
    issue_width: int = 1
    rob_entries: int = 128
    rs_int: int = 2
    rs_add: int = 3
    rs_mul: int = 2
    lsq_entries: int = 3
    int_cycles: int = 1
    add_cycles: int = 3
    mul_cycles: int = 20
    address_cycles: int = 1
    memory_cycles: int = 4
    int_units: int = 1
    add_units: int = 1
    mul_units: int = 1
    address_units: int = 1

    def validate(self):
        for name, value in vars(self).items():
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.issue_width > 4:
            raise ValueError("issue width must be between 1 and 4")


@dataclass(frozen=True)
class Instruction:
    pc: int
    op: str
    dest: str | None
    sources: tuple[str, ...]
    immediate: int
    text: str

    @property
    def group(self):
        if self.op in ("ld", "sd"):
            return "address"
        if self.op == "mult.d":
            return "mul"
        if self.op in ("add.d", "sub.d"):
            return "add"
        return "int"


@dataclass
class Program:
    config: Config
    instructions: list[Instruction]
    registers: dict[str, int | float]
    memory: dict[int, float]


@dataclass
class Operand:
    value: int | float | None = None
    tag: int | None = None
    available: int = 0

    def ready(self, cycle):
        return self.tag is None and self.available < cycle


@dataclass
class Entry:
    tag: int
    instruction: Instruction
    operands: list[Operand]
    issue: int
    ex_start: int | None = None
    ex_end: int | None = None
    mem_start: int | None = None
    mem_end: int | None = None
    wb: int | None = None
    commit: int | None = None
    commit_start: int | None = None
    ready: bool = False
    ready_cycle: int = 0
    value: int | float | None = None
    address: int | None = None
    address_cycle: int | None = None
    predicted_next: int | None = None
    predicted_taken: bool = False
    forwarded_from: int | None = None
    fault: str | None = None
    status: str = "inflight"
    squash_cycle: int | None = None
    squash_reason: str | None = None


@dataclass
class Execution:
    tag: int
    group: str
    end: int


@dataclass
class MemoryAccess:
    tag: int
    end: int
    store: bool = False
    forwarded: bool = False
    value: int | float | None = None


@dataclass
class Prediction:
    pc: int
    target: int
    taken: bool


def float32(value):
    """Round to IEEE 754 binary32, using round-to-nearest, ties-to-even."""
    try:
        return struct.unpack("!f", struct.pack("!f", value))[0]
    except OverflowError:
        return math.copysign(math.inf, value)


def check_address(address):
    if not isinstance(address, int) or address % 4 or not 0 <= address <= 252:
        raise ValueError(f"memory address {address} must be word-aligned in 0..252")


def parse_instruction(text, pc):
    tokens = text.replace(",", " ").split()
    op = tokens[0].lower()

    def reg(token, kind):
        token = token.upper()
        if not re.fullmatch(kind + r"(?:[0-9]|[12][0-9]|3[01])", token):
            raise ValueError(f"invalid {kind} register: {token}")
        return token

    if op in ("ld", "sd") and len(tokens) == 3:
        fp = reg(tokens[1], "F")
        match = re.fullmatch(r"([+-]?\d+)\(([Rr]\d+)\)", tokens[2])
        if not match:
            raise ValueError("load/store operand must be offset(Rn)")
        base = reg(match[2], "R")
        sources = (base,) if op == "ld" else (base, fp)
        return Instruction(pc, op, fp if op == "ld" else None,
                           sources, int(match[1]), text)
    if len(tokens) != 4:
        raise ValueError(f"invalid instruction: {text}")
    if op in ("beq", "bne"):
        return Instruction(pc, op, None,
                           (reg(tokens[1], "R"), reg(tokens[2], "R")),
                           int(tokens[3]), text)
    if op == "addi":
        return Instruction(pc, op, reg(tokens[1], "R"),
                           (reg(tokens[2], "R"),), int(tokens[3]), text)
    if op not in ("add", "sub", "add.d", "sub.d", "mult.d"):
        raise ValueError(f"unsupported opcode: {op}")
    kind = "F" if ".d" in op else "R"
    return Instruction(pc, op, reg(tokens[1], kind),
                       (reg(tokens[2], kind), reg(tokens[3], kind)), 0, text)


def parse_program(text):
    config = Config()
    instructions = []
    registers = {f"{kind}{i}": (0 if kind == "R" else 0.0)
                 for kind in ("R", "F") for i in range(32)}
    memory = {i: 0.0 for i in range(0, 256, 4)}
    seen = set()
    unit_fields = {
        "integer adder": ("rs_int", "int_cycles", "int_units"),
        "fp adder": ("rs_add", "add_cycles", "add_units"),
        "fp multiplier": ("rs_mul", "mul_cycles", "mul_units"),
        "load/store unit": ("lsq_entries", "address_cycles", "memory_cycles", "address_units"),
    }
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        normalized = " ".join(line.lower().split())
        if normalized.startswith(("cycles in", "unit cycles", "unit rs")):
            continue
        try:
            setting = re.match(r"^(issue\s+width|rob\s+entries)\b", line, re.I)
            if setting:
                key = " ".join(setting[1].lower().split())
                match = re.fullmatch(r"(?:issue\s+width|rob\s+entries)\s*=\s*([+-]?\d+)", line, re.I)
                if not match:
                    raise ValueError(f"{key} requires an integer after '='")
                if key in seen:
                    raise ValueError(f"duplicate {key} setting")
                seen.add(key)
                setattr(config, "issue_width" if key == "issue width" else "rob_entries", int(match[1]))
                continue
            unit = next((name for name in unit_fields if normalized.startswith(name)), None)
            if unit:
                if unit in seen:
                    raise ValueError(f"duplicate {unit} configuration")
                seen.add(unit)
                values = normalized[len(unit):].split()
                fields = unit_fields[unit]
                if len(values) != len(fields):
                    raise ValueError(f"{unit} requires {len(fields)} integer fields")
                for name, value in zip(fields, values):
                    setattr(config, name, int(value))
                continue
            if "=" in line:
                pattern = r"(mem\s*\[\s*\d+\s*\]|[rf]\d+)\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
                matches = list(re.finditer(pattern, line, re.I))
                if not matches or re.sub(pattern, "", line, flags=re.I).strip(" ,\t"):
                    raise ValueError("invalid register/memory initialization")
                for match in matches:
                    key = re.sub(r"\s", "", match[1]).upper()
                    if key in seen:
                        raise ValueError(f"duplicate initialization for {key}")
                    seen.add(key)
                    value = float(match[2])
                    if not math.isfinite(value):
                        raise ValueError("initial values must be finite")
                    if not key.startswith("R"):
                        value = float32(value)
                        if not math.isfinite(value):
                            raise ValueError("initial values must be finite in binary32")
                    if key.startswith("MEM"):
                        address = int(key[4:-1])
                        check_address(address)
                        memory[address] = value
                    else:
                        if key not in registers:
                            raise ValueError(f"invalid register: {key}")
                        if key.startswith("R"):
                            if not re.fullmatch(r"[+-]?\d+", match[2]):
                                raise ValueError("integer registers require integer values")
                            value = int(match[2])
                        if key == "R0" and value != 0:
                            raise ValueError("R0 is hardwired to zero")
                        registers[key] = value
                continue
            instructions.append(parse_instruction(line, len(instructions)))
        except ValueError as error:
            raise ValueError(f"Line {line_number}: {error}") from None
    config.validate()
    for instruction in instructions:
        if instruction.op in ("beq", "bne"):
            target = instruction.pc + 1 + instruction.immediate
            if not 0 <= target <= len(instructions):
                raise ValueError(f"branch at PC {instruction.pc * 4} targets outside the program")
    return Program(config, instructions, registers, memory)


def read_program(filename):
    return parse_program(Path(filename).read_text())
