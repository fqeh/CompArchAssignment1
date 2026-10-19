"""One result per cycle on the common data bus."""


def write_back(sim):
    candidates = [result for result in sim.results if result[0] < sim.cycle]
    if not candidates:
        return
    result = min(candidates, key=lambda item: (item[0], item[1]))
    sim.results.remove(result)
    _, tag, value = result
    entry = sim.entries[tag]
    entry.value = value
    entry.ready = True
    entry.ready_cycle = sim.cycle
    entry.wb = sim.cycle
    # Keep RAT producer tags until commit: an older completion must never
    # overwrite a mapping installed by a younger writer to the same register.
    for waiting in sim.entries.values():
        for operand in waiting.operands:
            if operand.tag == tag:
                operand.tag = None
                operand.value = value
                operand.available = sim.cycle
