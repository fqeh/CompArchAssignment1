"""Single-port loads, forwarding and speculation. Author: Ali Alfageeh."""


def mem(sim):
    if sim.port is not None:
        if sim.port['end'] < sim.cycle:
            sim.port = None
        else:
            if sim.port['kind'] != 'store' and sim.port['end'] == sim.cycle:
                finish_load(sim, sim.port)
            return
    for entry in sim.lsq:
        if entry.ins.op != 'ld' or not entry.ex or entry.ex[-1] >= sim.cycle or entry.mem or entry.fault:
            continue
        stores = [s for s in sim.lsq if s.id < entry.id and s.ins.op == 'sd'
                  and s.address == entry.address]
        source = max(stores, key=lambda e: e.id) if stores else None
        if source and not sim.ready(source.operands[1]):
            continue  # Wait for the youngest matching store, never stale data.
        latency = 1 if source else sim.config.memory_cycles
        entry.forwarded_from = source.id if source else None
        entry.mem = [sim.cycle, sim.cycle + latency - 1]
        sim.port = dict(entry=entry, end=entry.mem[-1], kind='forward' if source else 'load',
                        value=source.operands[1].value if source else None)
        if source:
            sim.stats['forwarded_loads'] += 1
        if sim.port['end'] == sim.cycle:
            finish_load(sim, sim.port)
        break


def finish_load(sim, transaction):
    entry = transaction['entry']
    value = transaction['value'] if transaction['kind'] == 'forward' else sim.memory[entry.address]
    sim.queue_result(entry, value)
    sim.lsq.remove(entry)
