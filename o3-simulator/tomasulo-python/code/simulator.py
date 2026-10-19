"""Cycle driver, recovery, and serializable execution results."""
from collections import deque
from copy import deepcopy
from dataclasses import asdict
from commit import commit
from exe import execute
from issue import issue
from mem import memory
from wb import write_back


class Simulator:
    def __init__(self, program, issue_width=None):
        self.program = program
        self.config = deepcopy(program.config)
        if issue_width is not None:
            self.config.issue_width = issue_width
        self.config.validate()
        self.registers = dict(program.registers)
        self.memory = dict(program.memory)
        self.pc = 0
        self.cycle = 0
        self.fetch_resume = 1
        self.next_tag = 0
        self.rob = deque()
        self.entries = {}
        self.history = []
        self.rat = {}
        self.rs = {group: [] for group in ("int", "add", "mul")}
        self.lsq = []
        self.executing = []
        self.results = []
        self.memory_access = None
        self.memory_available = 1
        self.forwarding = []
        self.btb = [None] * 8
        self.capacity = dict(int=self.config.rs_int, add=self.config.rs_add,
                             mul=self.config.rs_mul, address=self.config.lsq_entries)
        self.units = dict(int=self.config.int_units, add=self.config.add_units,
                          mul=self.config.mul_units, address=self.config.address_units)
        self.latency = dict(int=self.config.int_cycles, add=self.config.add_cycles,
                            mul=self.config.mul_cycles, address=self.config.address_cycles)
        self.stats = dict(issued=0, committed=0, squashed=0, branches=0,
                          mispredictions=0, memory_replays=0, forwarded_loads=0,
                          issue_stall_cycles=0)

    def squash_from(self, first_tag, pc, reason):
        removed = {tag for tag in self.rob if tag >= first_tag}
        for tag in removed:
            entry = self.entries.pop(tag)
            entry.status = "squashed"
            entry.squash_cycle = self.cycle
            entry.squash_reason = reason
        self.rob = deque(tag for tag in self.rob if tag not in removed)
        for group in self.rs:
            self.rs[group] = [tag for tag in self.rs[group] if tag not in removed]
        self.lsq = [tag for tag in self.lsq if tag not in removed]
        self.executing = [job for job in self.executing if job.tag not in removed]
        self.results = [result for result in self.results if result[1] not in removed]
        self.forwarding = [access for access in self.forwarding if access.tag not in removed]
        if self.memory_access and self.memory_access.tag in removed:
            assert not self.memory_access.store
            self.memory_access = None
            self.memory_available = self.cycle + 1
        # Rebuild mappings from surviving instructions in program order.
        self.rat.clear()
        for tag in self.rob:
            dest = self.entries[tag].instruction.dest
            if dest and dest != "R0":
                self.rat[dest] = tag
        self.pc = pc
        self.fetch_resume = self.cycle + 2
        self.stats["squashed"] += len(removed)

    def check_memory_violation(self, store):
        violations = [entry for entry in self.entries.values()
                      if entry.tag > store.tag and entry.instruction.op == "ld"
                      and entry.mem_start is not None and entry.address == store.address
                      and (entry.forwarded_from is None or entry.forwarded_from < store.tag)]
        if violations:
            load = min(violations, key=lambda entry: entry.tag)
            self.stats["memory_replays"] += 1
            self.squash_from(load.tag, load.instruction.pc, "memory ordering replay")

    def run(self, max_cycles=100000):
        if max_cycles < 1:
            raise ValueError("max_cycles must be positive")
        while self.rob or self.pc < len(self.program.instructions):
            if self.cycle >= max_cycles:
                raise RuntimeError(f"simulation exceeded {max_cycles} cycles (possible infinite loop)")
            self.cycle += 1
            # Timestamp checks enforce inter-stage boundaries. Resources freed
            # earlier in this tick may be reused by ISSUE at the end of the tick.
            commit(self)
            write_back(self)
            execute(self)
            memory(self)
            issue(self)
        return self.result()

    def result(self):
        records = []
        for entry in self.history:
            record = asdict(entry)
            record["pc_bytes"] = entry.instruction.pc * 4
            records.append(record)
        return {
            "config": asdict(self.config),
            "cycles": self.cycle,
            "ipc": self.stats["committed"] / self.cycle if self.cycle else 0,
            "statistics": dict(self.stats),
            "registers": dict(self.registers),
            "memory": {str(address): value for address, value in self.memory.items() if value != 0},
            "instructions": records,
        }
