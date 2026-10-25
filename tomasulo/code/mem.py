"""Byte-aware loads, forwarding and speculation. Author: Ali Alfageeh."""
from init import pack_float32, unpack_float32


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
        sources = select_byte_sources(sim, entry)
        contributing = {store.id: store for store in sources if store is not None}
        if any(not sim.ready(store.operands[1]) for store in contributing.values()):
            continue  # Wait only for stores whose bytes this load will consume.
        full_forward = all(source is not None for source in sources)
        latency = 1 if full_forward else sim.config.memory_cycles
        entry.byte_sources = [store.id if store else 0 for store in sources]
        entry.forwarded_sources = sorted(contributing)
        if full_forward and len(contributing) == 1:
            entry.forwarded_from = entry.forwarded_sources[0]
        # Snapshot memory, then overlay each byte from its newest older store.
        data = bytearray(sim.memory.read_bytes(entry.address))
        encoded = {tag: pack_float32(store.operands[1].value)
                   for tag, store in contributing.items()}
        for offset, store in enumerate(sources):
            if store is not None:
                data[offset] = encoded[store.id][entry.address + offset - store.address]
        entry.mem = [sim.cycle, sim.cycle + latency - 1]
        sim.port = dict(entry=entry, end=entry.mem[-1],
                        kind='forward' if full_forward else 'load', data=bytes(data))
        if contributing:
            sim.stats['forwarded_loads'] += 1
            if not full_forward:
                sim.stats['partial_forwarded_loads'] += 1
        if sim.port['end'] == sim.cycle:
            finish_load(sim, sim.port)
        break


def select_byte_sources(sim, load):
    """For each load byte, select its youngest known older overlapping store."""
    sources = [None] * 4
    for store in reversed(sim.lsq):
        if store.id >= load.id or store.ins.op != 'sd' or store.address is None:
            continue
        first = max(store.address, load.address)
        last = min(store.address + 4, load.address + 4)
        for address in range(first, last):
            offset = address - load.address
            if sources[offset] is None:
                sources[offset] = store
    return sources


def finish_load(sim, transaction):
    entry = transaction['entry']
    sim.queue_result(entry, unpack_float32(transaction['data']))
    sim.lsq.remove(entry)
