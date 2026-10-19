"""Oldest-ready execution; pipelined FP and unpipelined integer/address FUs."""
from init import Execution, Prediction, check_address, float32


def execute(sim):
    for group in ("int", "add", "mul", "address"):
        queue = sim.lsq if group == "address" else sim.rs[group]
        active = sum(job.group == group for job in sim.executing)
        slots = sim.units[group]
        if group in ("int", "address"):
            slots -= active
        for tag in list(queue):
            if slots <= 0:
                break
            entry = sim.entries[tag]
            if entry.issue >= sim.cycle or entry.ex_start is not None:
                continue
            operands = entry.operands[:1] if group == "address" else entry.operands
            if not all(operand.ready(sim.cycle) for operand in operands):
                continue
            entry.ex_start = sim.cycle
            sim.executing.append(Execution(tag, group, sim.cycle + sim.latency[group] - 1))
            if group != "address":
                queue.remove(tag)
            slots -= 1
    # Complete in age order so an older redirect wins over younger work.
    for job in sorted(list(sim.executing), key=lambda item: item.tag):
        if job.end != sim.cycle or job.tag not in sim.entries:
            continue
        sim.executing.remove(job)
        entry = sim.entries[job.tag]
        entry.ex_end = sim.cycle
        instruction = entry.instruction
        values = [operand.value for operand in entry.operands]
        op = instruction.op
        if job.group == "address":
            entry.address = values[0] + instruction.immediate
            entry.address_cycle = sim.cycle
            try:
                check_address(entry.address)
            except ValueError as error:
                # Speculative faults become visible only at in-order commit.
                entry.fault = str(error)
                entry.ready = True
                entry.ready_cycle = sim.cycle
                continue
            if op == "sd":
                sim.check_memory_violation(entry)
        elif op in ("beq", "bne"):
            taken = (values[0] == values[1]) if op == "beq" else (values[0] != values[1])
            target = instruction.pc + 1 + instruction.immediate
            actual_next = target if taken else instruction.pc + 1
            sim.btb[instruction.pc & 7] = Prediction(instruction.pc, target, taken)
            entry.ready = True
            entry.ready_cycle = sim.cycle
            sim.stats["branches"] += 1
            if entry.predicted_taken != taken or entry.predicted_next != actual_next:
                sim.stats["mispredictions"] += 1
                sim.squash_from(entry.tag + 1, actual_next, "branch misprediction")
        else:
            if op == "addi":
                value = values[0] + instruction.immediate
            elif op in ("add", "add.d"):
                value = values[0] + values[1]
            elif op in ("sub", "sub.d"):
                value = values[0] - values[1]
            else:
                value = values[0] * values[1]
            if job.group in ("add", "mul"):
                value = float32(value)
            sim.results.append((sim.cycle, entry.tag, value))
