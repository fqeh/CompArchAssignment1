"""In-order, sequential renaming within a multi-issue bundle."""
from init import Entry, Operand


def source_operand(sim, register):
    tag = sim.rat.get(register)
    if tag is None:
        return Operand(value=sim.registers[register])
    producer = sim.entries[tag]
    if producer.ready and not producer.fault:
        return Operand(value=producer.value, available=producer.ready_cycle)
    return Operand(tag=tag)


def issue(sim):
    if sim.cycle < sim.fetch_resume:
        return
    for _ in range(sim.config.issue_width):
        if sim.pc == len(sim.program.instructions):
            break
        instruction = sim.program.instructions[sim.pc]
        group = instruction.group
        queue = sim.lsq if group == "address" else sim.rs[group]
        if len(sim.rob) >= sim.config.rob_entries or len(queue) >= sim.capacity[group]:
            sim.stats["issue_stall_cycles"] += 1
            break
        # Read sources BEFORE renaming this destination (e.g., Addi R1 R1 -1).
        operands = [source_operand(sim, reg) for reg in instruction.sources]
        tag = sim.next_tag
        sim.next_tag += 1
        entry = Entry(tag, instruction, operands, sim.cycle)
        sim.entries[tag] = entry
        sim.history.append(entry)
        sim.rob.append(tag)
        queue.append(tag)
        if instruction.dest and instruction.dest != "R0":
            sim.rat[instruction.dest] = tag
        sim.pc += 1
        if instruction.op in ("beq", "bne"):
            predictor = sim.btb[instruction.pc & 7]
            if predictor and predictor.pc == instruction.pc and predictor.taken:
                entry.predicted_taken = True
                sim.pc = predictor.target
            entry.predicted_next = sim.pc
        sim.stats["issued"] += 1
