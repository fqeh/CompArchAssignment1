"""Cycle-accurate teaching model. Assignment author: Ali Alfageeh.

Derived from the module organization and algorithm of Qing's 2017 starter.
ALU values use Python numbers; memory uses four-byte IEEE 754 binary32 values.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from init import validate_address


@dataclass
class Operand:
    value: float | int = 0
    tag: int | None = None
    ready_at: int = 0


@dataclass
class Entry:
    id: int
    pc: int
    ins: object
    issue: int
    operands: list
    ex: list = field(default_factory=list)
    mem: list = field(default_factory=list)
    wb: int | None = None
    commit: int | None = None
    value: float | int | None = None
    address: int | None = None
    predicted_next: int | None = None
    status: str = 'active'
    squash_reason: str | None = None
    forwarded_from: int | None = None
    byte_sources: list = field(default_factory=list)
    forwarded_sources: list = field(default_factory=list)
    fault: str | None = None
    resolved_at: int | None = None


class Simulator:
    """One CDB and one in-order retirement slot, independent of issue width."""
    def __init__(self, program, issue_width=None, max_cycles=100000):
        self.program = deepcopy(program)
        self.config = self.program.config
        self.width = self.config.issue_width if issue_width is None else issue_width
        if not isinstance(self.width, int) or not 1 <= self.width <= 4:
            raise ValueError('Issue width must be between 1 and 4')
        self.max_cycles = max_cycles
        self.regs = self.program.registers.copy()
        self.memory = self.program.memory.copy()
        self.rat = {}
        self.rob = []
        self.history = []
        self.rs = {name: [] for name in ('integer', 'fp_add', 'fp_mul')}
        self.lsq = []
        self.jobs = []
        self.results = []
        self.port = None
        self.pc = 0
        self.cycle = 0
        self.next_id = 1
        self.fetch_after = 1
        self.btb = [None] * 8
        self.stats = dict(issued=0, branch_predictions=0, branch_mispredictions=0,
                          memory_replays=0, structural_stalls=0, forwarded_loads=0,
                          partial_forwarded_loads=0)

    def source(self, register):
        if register == 'R0':
            return Operand()
        tag = self.rat.get(register)
        if tag is None:
            return Operand(self.regs[register])
        producer = next(e for e in self.rob if e.id == tag)
        if producer.wb is not None:
            return Operand(producer.value, ready_at=producer.wb)
        return Operand(tag=tag)

    def ready(self, operand):
        return operand.tag is None and operand.ready_at < self.cycle

    def active(self, entry):
        return entry.status == 'active'

    def queue_result(self, entry, value):
        entry.value = value
        self.results.append((self.cycle, entry.id, entry))

    def recover(self, first_id, correct_pc, reason):
        """Remove every younger effect and rebuild renaming from surviving ROB."""
        for entry in self.rob:
            if entry.id >= first_id:
                entry.status = 'squashed'
                entry.squash_reason = reason
        self.rob = [e for e in self.rob if self.active(e)]
        self.lsq = [e for e in self.lsq if self.active(e)]
        for unit in self.rs:
            self.rs[unit] = [e for e in self.rs[unit] if self.active(e)]
        self.jobs = [job for job in self.jobs if self.active(job['entry'])]
        self.results = [result for result in self.results if self.active(result[2])]
        if self.port and not self.active(self.port['entry']):
            self.port = None
        self.rat.clear()
        for entry in self.rob:
            if entry.ins.dest and entry.ins.dest != 'R0':
                self.rat[entry.ins.dest] = entry.id
        self.pc = correct_pc
        self.fetch_after = self.cycle + 2

    def check_memory_violation(self, store):
        # Loads are retained in the ROB after leaving the LSQ, so violations
        # are detected even after a speculative load has already broadcast.
        violations = []
        for load in self.rob:
            if load.id <= store.id or load.ins.op != 'ld' or not load.mem:
                continue
            # A later store can hide an older alias on some or all bytes.
            first = max(store.address, load.address)
            last = min(store.address + 4, load.address + 4)
            if any(load.byte_sources[a - load.address] < store.id
                   for a in range(first, last)):
                violations.append(load)
        if violations:
            load = min(violations, key=lambda e: e.id)
            self.stats['memory_replays'] += 1
            self.recover(load.id, load.pc, 'memory_order')

    def run(self):
        from commit import commit
        from wb import wb
        from mem import mem
        from exe import exe
        from issue import issue
        while self.rob or 0 <= self.pc < len(self.program.instructions):
            self.cycle += 1
            if self.cycle > self.max_cycles:
                raise RuntimeError(f'Exceeded {self.max_cycles} cycles (possible infinite loop)')
            commit(self)
            wb(self)
            mem(self)
            exe(self)
            issue(self)
            self.regs['R0'] = 0
        return self.result()

    def result(self):
        rows = []
        for e in self.history:
            rows.append(dict(id=e.id, pc=e.pc, text=e.ins.text, issue=e.issue,
                             ex=e.ex, mem=e.mem, wb=e.wb, commit=e.commit,
                             status=e.status, squash_reason=e.squash_reason,
                             forwarded_from=e.forwarded_from,
                             byte_sources=e.byte_sources, forwarded_sources=e.forwarded_sources))
        return dict(author='Ali Alfageeh', issue_width=self.width,
                    cycles=self.cycle, committed=sum(e.commit is not None for e in self.history),
                    registers=self.regs.copy(),
                    memory={str(a): v for a, v in self.memory.items() if v != 0},
                    memory_bytes=list(self.memory.data), byte_order='little',
                    instructions=rows, stats=self.stats.copy())
