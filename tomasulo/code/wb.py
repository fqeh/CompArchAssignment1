"""Single common-data-bus arbitration. Assignment author: Ali Alfageeh."""


def wb(sim):
    eligible = [r for r in sim.results if r[0] < sim.cycle]
    if not eligible:
        return
    result = min(eligible, key=lambda r: (r[0], r[1]))
    sim.results.remove(result)
    entry = result[2]
    entry.wb = sim.cycle
    # Tags remain in the RAT until their producer commits. An older WAW
    # producer therefore cannot overwrite a newer register mapping.
    for waiting in sim.rob:
        for operand in waiting.operands:
            if operand.tag == entry.id:
                operand.tag = None
                operand.value = entry.value
                operand.ready_at = sim.cycle
