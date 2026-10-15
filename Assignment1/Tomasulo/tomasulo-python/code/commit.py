"""Retire one ROB head per cycle; only committing stores change memory."""
from model import MemoryAccess


def retire(cpu, entry):
    entry.commit = cpu.cycle
    cpu.rob.pop(0)
    destination = entry.instruction.dest
    if destination and destination != "R0":
        cpu.registers[destination] = entry.result
        if cpu.rat.get(destination) == entry.tag:
            del cpu.rat[destination]


def commit(cpu):
    if not cpu.rob:
        return
    entry = cpu.rob[0]
    if entry.error and entry.complete is not None and entry.complete < cpu.cycle:
        raise ValueError(f"Byte PC {entry.pc * 4}: {entry.error}")
    if entry.instruction.op == "sd":
        if (entry.address is not None and entry.ex_end < cpu.cycle
              and entry.operands[1].ready(cpu.cycle)
              and entry.mem_start is None and cpu.memory_access is None):
            entry.mem_start = cpu.cycle
            cpu.memory_access = MemoryAccess(entry,
                cpu.cycle + cpu.config.memory_latency - 1, entry.operands[1].value)
    elif entry.instruction.branch:
        if entry.complete is not None and entry.complete < cpu.cycle:
            retire(cpu, entry)
    elif entry.wb is not None and entry.wb < cpu.cycle:
        retire(cpu, entry)
