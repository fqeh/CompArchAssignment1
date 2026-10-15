"""Cycle-driven Tomasulo core; architectural state changes at retirement."""
from copy import deepcopy

from commit import commit
from exe import exe
from issue import issue
from mem import mem
from wb import wb


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
        self.next_tag = 1
        self.fetch_after = 1
        self.rat = {}
        self.rob = []
        self.lsq = []
        self.stations = {name: [] for name in ("integer", "fp_add", "fp_mul")}
        self.executing = []
        self.memory_access = None
        self.history = []
        self.btb = [None] * 8
        self.branches = self.mispredictions = self.memory_replays = self.issue_stalls = 0

    def squash(self, first_tag, target):
        for entry in self.rob:
            if entry.tag >= first_tag:
                entry.squashed = self.cycle
        self.rob = [entry for entry in self.rob if entry.tag < first_tag]
        self.lsq = [entry for entry in self.lsq if entry.tag < first_tag]
        for unit, queue in self.stations.items():
            self.stations[unit] = [entry for entry in queue if entry.tag < first_tag]
        self.executing = [task for task in self.executing if task.entry.tag < first_tag]
        if self.memory_access and self.memory_access.entry.tag >= first_tag:
            self.memory_access = None
        self.rat.clear()
        for entry in self.rob:
            destination = entry.instruction.dest
            if destination and destination != "R0":
                self.rat[destination] = entry.tag
        self.pc = target
        self.fetch_after = self.cycle + 2

    def step(self):
        self.cycle += 1
        commit(self)
        wb(self)
        mem(self)
        exe(self)
        issue(self)

    def run(self, max_cycles=100000):
        if max_cycles < 1:
            raise ValueError("Maximum cycles must be positive")
        while self.pc < len(self.program.instructions) or self.rob:
            if self.cycle >= max_cycles:
                raise RuntimeError(f"Exceeded {max_cycles} cycles (possible infinite loop)")
            self.step()
        return self

    @property
    def committed(self):
        return [entry for entry in self.history if entry.commit is not None]
