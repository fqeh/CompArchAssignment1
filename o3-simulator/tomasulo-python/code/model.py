"""Typed state shared by the five Tomasulo pipeline stages."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UnitConfig:
    stations: int
    latency: int
    count: int = 1


@dataclass
class Config:
    integer: UnitConfig = field(default_factory=lambda: UnitConfig(2, 1))
    fp_add: UnitConfig = field(default_factory=lambda: UnitConfig(3, 3))
    fp_mul: UnitConfig = field(default_factory=lambda: UnitConfig(2, 20))
    address: UnitConfig = field(default_factory=lambda: UnitConfig(3, 1))
    memory_latency: int = 4
    rob_entries: int = 128
    issue_width: int = 1

    def validate(self):
        if self.issue_width not in range(1, 5):
            raise ValueError("Issue width must be between 1 and 4")
        if self.rob_entries < 1 or self.memory_latency < 1:
            raise ValueError("ROB entries and memory latency must be positive")
        for unit in (self.integer, self.fp_add, self.fp_mul, self.address):
            if min(unit.stations, unit.latency, unit.count) < 1:
                raise ValueError("RS counts, EX latencies, and FU counts must be positive")


@dataclass(frozen=True)
class Instruction:
    op: str
    text: str
    dest: Optional[str] = None
    sources: tuple = ()
    immediate: int = 0

    @property
    def unit(self):
        if self.op in ("ld", "sd"):
            return "address"
        if self.op in ("add.d", "sub.d"):
            return "fp_add"
        if self.op == "mult.d":
            return "fp_mul"
        return "integer"

    @property
    def branch(self):
        return self.op in ("beq", "bne")


@dataclass
class Program:
    config: Config
    instructions: list
    registers: dict
    memory: dict


@dataclass
class Operand:
    value: object = 0
    tag: Optional[int] = None
    ready_at: int = 0

    def ready(self, cycle):
        return self.tag is None and self.ready_at < cycle


@dataclass
class Entry:
    tag: int
    pc: int
    instruction: Instruction
    operands: list
    issue: int
    ex_start: Optional[int] = None
    ex_end: Optional[int] = None
    mem_start: Optional[int] = None
    mem_end: Optional[int] = None
    wb: Optional[int] = None
    commit: Optional[int] = None
    complete: Optional[int] = None
    result: object = None
    address: Optional[int] = None
    predicted_pc: Optional[int] = None
    squashed: Optional[int] = None
    forwarded: bool = False
    error: Optional[str] = None


@dataclass
class Execution:
    entry: Entry
    end: int


@dataclass
class MemoryAccess:
    entry: Entry
    end: int
    value: object


@dataclass
class Prediction:
    pc: int
    target: int
    taken: bool
