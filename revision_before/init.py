"""Input parsing and processor state. Assignment author: Ali Alfageeh.

Refactored from Qing's 2017 Tomasulo teaching simulator. The original source is
preserved separately; this module replaces mutable namedtuple-class state.
"""
from dataclasses import dataclass, field
from decimal import Decimal
import re


@dataclass
class UnitConfig:
    rs: int
    ex: int
    count: int = 1


@dataclass
class Config:
    integer: UnitConfig = field(default_factory=lambda: UnitConfig(2, 1))
    fp_add: UnitConfig = field(default_factory=lambda: UnitConfig(3, 3))
    fp_mul: UnitConfig = field(default_factory=lambda: UnitConfig(2, 20))
    load_store: UnitConfig = field(default_factory=lambda: UnitConfig(3, 1))
    memory_cycles: int = 4
    rob_entries: int = 128
    issue_width: int = 1


@dataclass
class Instruction:
    op: str
    dest: str | None
    sources: list
    immediate: int = 0
    text: str = ''

    @property
    def unit(self):
        if self.op in ('ld', 'sd'):
            return 'load_store'
        if self.op in ('add.d', 'sub.d'):
            return 'fp_add'
        if self.op == 'mult.d':
            return 'fp_mul'
        return 'integer'


@dataclass
class Program:
    instructions: list
    config: Config
    registers: dict
    memory: dict


def register(token, kind):
    token = token.upper()
    if not re.fullmatch(kind + r'(?:[0-9]|[12][0-9]|3[01])', token):
        raise ValueError(f'Invalid {kind} register: {token}')
    return token


def parse_program(text, legacy_branch_bytes=False):
    """Parse the assignment table, initial state and case-insensitive ISA.

    Branch offsets are words, as in PC + 4 + (offset << 2). The explicit legacy
    option converts starter byte offsets to words (and requires multiples of 4).
    """
    cfg = Config()
    regs = {f'{k}{i}': 0 for k in ('R', 'F') for i in range(32)}
    memory = {i: 0 for i in range(0, 256, 4)}
    instructions = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split('#', 1)[0].split('//', 1)[0].strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith(('cycles in', 'configuration', 'list of instructions')):
            continue
        found = False
        for label, attr in [('integer adder', 'integer'), ('fp adder', 'fp_add'),
                            ('fp multiplier', 'fp_mul'), ('load/store unit', 'load_store')]:
            if low.startswith(label):
                nums = line[len(label):].split()
                try:
                    vals = [int(x) for x in nums]
                except ValueError as exc:
                    raise ValueError(f'Line {number}: invalid hardware row') from exc
                expected = 4 if attr == 'load_store' else 3
                if len(vals) != expected or any(x < 1 for x in vals):
                    raise ValueError(f'Line {number}: {label} requires {expected} positive integers')
                setattr(cfg, attr, UnitConfig(vals[0], vals[1], vals[-1]))
                if attr == 'load_store':
                    cfg.memory_cycles = vals[2]
                found = True
                break
        if found:
            continue
        match = re.fullmatch(r'(rob\s+entries|issue\s+width)\s*=\s*(-?\d+)', low)
        if match:
            value = int(match[2])
            if match[1].startswith('rob'):
                if value < 1:
                    raise ValueError('ROB entries must be positive')
                cfg.rob_entries = value
            else:
                if not 1 <= value <= 4:
                    raise ValueError('Issue width must be between 1 and 4')
                cfg.issue_width = value
            continue
        if '=' in line:
            for assignment in line.split(','):
                assignment = assignment.strip()
                match = re.fullmatch(r'(R\d+|F\d+|Mem\[\d+\])\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)', assignment, re.I)
                if not match:
                    raise ValueError(f'Line {number}: invalid initialization: {assignment}')
                name, val = match.groups()
                if name.lower().startswith('mem'):
                    address = int(re.search(r'\d+', name)[0])
                    validate_address(address)
                    memory[address] = float(val)
                elif name[0].upper() == 'R':
                    name = register(name, 'R')
                    integer = Decimal(val)
                    if integer != integer.to_integral_value():
                        raise ValueError('Integer register initial values must be integers')
                    if name == 'R0' and integer != 0:
                        raise ValueError('R0 is hardwired to zero')
                    regs[name] = int(integer)
                else:
                    regs[register(name, 'F')] = float(val)
            continue
        parts = line.replace(',', ' ').split()
        op = parts[0].lower()
        try:
            if op in ('ld', 'sd'):
                if len(parts) != 3:
                    raise ValueError('load/store requires two operands')
                freg = register(parts[1], 'F')
                address = re.fullmatch(r'([+-]?\d+)\((R\d+)\)', parts[2], re.I)
                if not address:
                    raise ValueError('memory operand must be offset(Rn)')
                base = register(address[2], 'R')
                ins = Instruction(op, freg if op == 'ld' else None,
                                  [base] if op == 'ld' else [base, freg], int(address[1]), line)
            elif op in ('beq', 'bne'):
                if len(parts) != 4:
                    raise ValueError('branch requires three operands')
                offset = int(parts[3])
                if legacy_branch_bytes:
                    if offset % 4:
                        raise ValueError('legacy branch byte offset must be divisible by four')
                    offset //= 4
                ins = Instruction(op, None, [register(parts[1], 'R'), register(parts[2], 'R')], offset, line)
            elif op in ('add', 'sub', 'addi', 'add.d', 'sub.d', 'mult.d'):
                if len(parts) != 4:
                    raise ValueError('ALU instruction requires three operands')
                kind = 'F' if '.' in op else 'R'
                dest, first = register(parts[1], kind), register(parts[2], kind)
                if op == 'addi':
                    ins = Instruction(op, dest, [first], int(parts[3]), line)
                else:
                    ins = Instruction(op, dest, [first, register(parts[3], kind)], 0, line)
            else:
                raise ValueError(f'Unsupported opcode: {parts[0]}')
        except (ValueError, IndexError) as exc:
            raise ValueError(f'Line {number}: {exc}') from exc
        instructions.append(ins)
    return Program(instructions, cfg, regs, memory)


def validate_address(address):
    if not isinstance(address, int) or address % 4 or not 0 <= address <= 252:
        raise ValueError(f'Address {address} must be word-aligned in 0..252')
