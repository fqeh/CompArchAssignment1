"""Single-width in-order retirement; stores access memory at the ROB head."""
from init import MemoryAccess


def retire(sim, entry):
    assert sim.rob[0] == entry.tag
    sim.rob.popleft()
    dest = entry.instruction.dest
    if dest and dest != "R0":
        sim.registers[dest] = entry.value
        if sim.rat.get(dest) == entry.tag:
            del sim.rat[dest]
    if entry.tag in sim.lsq:
        sim.lsq.remove(entry.tag)
    entry.commit = sim.cycle
    entry.status = "committed"
    del sim.entries[entry.tag]
    sim.stats["committed"] += 1


def commit(sim):
    if not sim.rob:
        return
    entry = sim.entries[sim.rob[0]]
    if entry.fault:
        raise ValueError(f"PC {entry.instruction.pc * 4}: {entry.fault}")
    if entry.instruction.op == "sd":
        if entry.commit_start is not None:
            return
        if (entry.address_cycle is None or entry.address_cycle >= sim.cycle
                or not entry.operands[1].ready(sim.cycle)):
            return
        if sim.memory_access is not None or sim.cycle < sim.memory_available:
            return
        entry.commit_start = sim.cycle
        entry.mem_start = sim.cycle
        sim.memory_access = MemoryAccess(entry.tag, sim.cycle + sim.config.memory_cycles - 1,
                                         store=True, value=entry.operands[1].value)
    elif entry.ready and entry.ready_cycle < sim.cycle:
        retire(sim, entry)
