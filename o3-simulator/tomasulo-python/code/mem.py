"""Single memory port, one-cycle store forwarding, and speculative loads."""
from commit import retire
from init import MemoryAccess, float32


def memory(sim):
    forwarding_used = False
    for tag in list(sim.lsq):
        entry = sim.entries[tag]
        if (entry.instruction.op != "ld" or entry.fault
                or entry.address_cycle is None or entry.address_cycle >= sim.cycle
                or entry.mem_start is not None):
            continue
        older_matches = [sim.entries[older] for older in sim.lsq
                         if older < tag and sim.entries[older].instruction.op == "sd"
                         and sim.entries[older].address == entry.address]
        source = max(older_matches, key=lambda candidate: candidate.tag, default=None)
        if source:
            if (forwarding_used or source.address_cycle >= sim.cycle
                    or not source.operands[1].ready(sim.cycle)):
                continue
            entry.mem_start = sim.cycle
            entry.forwarded_from = source.tag
            sim.forwarding.append(MemoryAccess(tag, sim.cycle, forwarded=True,
                                               value=source.operands[1].value))
            forwarding_used = True
            sim.stats["forwarded_loads"] += 1
        elif sim.memory_access is None and sim.cycle >= sim.memory_available:
            # Unresolved older stores allow speculation. A later alias triggers
            # replay of the load and its younger dependent instructions.
            entry.mem_start = sim.cycle
            sim.memory_access = MemoryAccess(tag, sim.cycle + sim.config.memory_cycles - 1)
    completed = [access for access in sim.forwarding if access.end == sim.cycle]
    if sim.memory_access and sim.memory_access.end == sim.cycle:
        completed.append(sim.memory_access)
        sim.memory_access = None
        sim.memory_available = sim.cycle + 1
    for access in sorted(completed, key=lambda item: item.tag):
        if access in sim.forwarding:
            sim.forwarding.remove(access)
        entry = sim.entries[access.tag]
        entry.mem_end = sim.cycle
        if access.store:
            sim.memory[entry.address] = float32(access.value)
            retire(sim, entry)
        else:
            value = access.value if access.forwarded else sim.memory[entry.address]
            sim.results.append((sim.cycle, entry.tag, float32(value)))
            sim.lsq.remove(entry.tag)
