"""In-order retirement and precise stores. Assignment author: Ali Alfageeh."""


def commit(sim):
    if not sim.rob:
        return
    entry = sim.rob[0]
    if entry.fault:
        raise ValueError(f'Instruction {entry.id} ({entry.ins.text}): {entry.fault}')
    if entry.ins.op == 'sd':
        if not entry.ex or entry.ex[-1] >= sim.cycle or not sim.ready(entry.operands[1]):
            return
        if not entry.mem:
            if sim.port is not None and sim.port['end'] >= sim.cycle:
                return
            end = sim.cycle + sim.config.memory_cycles - 1
            entry.mem = [sim.cycle, end]
            sim.port = dict(entry=entry, end=end, kind='store')
        if entry.mem[-1] != sim.cycle:
            return
        # Only the ROB head can update memory, at its retirement cycle.
        sim.memory[entry.address] = entry.operands[1].value
        sim.lsq.remove(entry)
    elif entry.ins.op in ('beq', 'bne'):
        if entry.resolved_at is None or entry.resolved_at >= sim.cycle:
            return
    elif entry.wb is None or entry.wb >= sim.cycle:
        return
    if entry.ins.dest and entry.ins.dest != 'R0':
        sim.regs[entry.ins.dest] = entry.value
        if sim.rat.get(entry.ins.dest) == entry.id:
            del sim.rat[entry.ins.dest]
    entry.commit = sim.cycle
    entry.status = 'committed'
    sim.rob.pop(0)
