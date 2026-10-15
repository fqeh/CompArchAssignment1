"""Single-port memory, store forwarding, and speculative load accesses."""
from model import MemoryAccess
from commit import retire


def mem(cpu):
    # An operation finishing this cycle still occupies the port this cycle.
    if cpu.memory_access is None:
        for entry in cpu.lsq:
            if (entry.instruction.op != "ld" or entry.address is None
                    or entry.ex_end >= cpu.cycle or entry.mem_start is not None):
                continue
            stores = [older for older in cpu.lsq if older.tag < entry.tag
                      and older.instruction.op == "sd" and older.address == entry.address]
            store = stores[-1] if stores else None
            if store and not store.operands[1].ready(cpu.cycle):
                continue
            entry.forwarded = store is not None
            value = store.operands[1].value if store else cpu.memory[entry.address]
            latency = 1 if store else cpu.config.memory_latency
            entry.mem_start = cpu.cycle
            cpu.memory_access = MemoryAccess(entry, cpu.cycle + latency - 1, value)
            break
    access = cpu.memory_access
    if access and access.end == cpu.cycle:
        entry = access.entry
        entry.mem_end = cpu.cycle
        if entry.instruction.op == "sd":
            cpu.memory[entry.address] = access.value
            retire(cpu, entry)
            cpu.lsq.remove(entry)
        else:
            entry.result = access.value
            entry.complete = cpu.cycle
            cpu.lsq.remove(entry)
        cpu.memory_access = None
