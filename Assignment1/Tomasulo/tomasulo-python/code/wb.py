"""One common data bus: broadcast the oldest eligible result each cycle."""


def wb(cpu):
    candidates = [entry for entry in cpu.rob
                  if entry.complete is not None and entry.complete < cpu.cycle
                  and entry.wb is None and entry.error is None
                  and entry.instruction.dest is not None]
    if not candidates:
        return
    entry = min(candidates, key=lambda item: item.tag)
    entry.wb = cpu.cycle
    for consumer in cpu.rob:
        for operand in consumer.operands:
            if operand.tag == entry.tag:
                operand.tag = None
                operand.value = entry.result
                operand.ready_at = cpu.cycle
