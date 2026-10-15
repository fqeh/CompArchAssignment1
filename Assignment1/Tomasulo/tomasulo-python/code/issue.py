"""In-order, 1--4-wide issue with immediate renaming within each bundle."""
from model import Entry, Operand


def source(cpu, name):
    tag = cpu.rat.get(name)
    if tag is None:
        return Operand(cpu.registers[name])
    producer = next(entry for entry in cpu.rob if entry.tag == tag)
    if producer.wb is not None:
        return Operand(producer.result, ready_at=producer.wb)
    return Operand(tag=tag)


def issue(cpu):
    if cpu.cycle < cpu.fetch_after:
        return
    for _ in range(cpu.config.issue_width):
        if cpu.pc == len(cpu.program.instructions):
            return
        instruction = cpu.program.instructions[cpu.pc]
        unit = instruction.unit
        queue = cpu.lsq if unit == "address" else cpu.stations[unit]
        if (len(cpu.rob) == cpu.config.rob_entries or
                len(queue) == getattr(cpu.config, unit).stations):
            cpu.issue_stalls += 1
            return  # A younger instruction cannot bypass a blocked instruction.
        entry = Entry(cpu.next_tag, cpu.pc, instruction,
                      [source(cpu, name) for name in instruction.sources], cpu.cycle)
        cpu.next_tag += 1
        cpu.rob.append(entry)
        cpu.history.append(entry)
        queue.append(entry)
        if instruction.dest and instruction.dest != "R0":
            cpu.rat[instruction.dest] = entry.tag
        next_pc = cpu.pc + 1
        if instruction.branch:
            prediction = cpu.btb[cpu.pc % 8]
            if prediction and prediction.pc == cpu.pc and prediction.taken:
                next_pc = prediction.target
            entry.predicted_pc = next_pc
        cpu.pc = next_pc
