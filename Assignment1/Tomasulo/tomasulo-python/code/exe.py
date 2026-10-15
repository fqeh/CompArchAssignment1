"""Out-of-order scheduling, functional-unit completion, and branch recovery."""
from init import address_valid
from model import Execution, Prediction


def finish(cpu, entry):
    instruction = entry.instruction
    values = [operand.value for operand in entry.operands]
    entry.ex_end = cpu.cycle
    if instruction.unit == "address":
        entry.address = values[0] + instruction.immediate
        if not address_valid(entry.address):
            entry.error = f"Invalid memory byte address {entry.address}; expected aligned 0..252"
            entry.address = None
            entry.complete = cpu.cycle  # Report faults precisely, only at the ROB head.
            return
        if instruction.op == "sd":
            # Loads can bypass unknown store addresses. Replay any younger load
            # that accessed this location before this store's address was known.
            conflicts = [younger for younger in cpu.rob if younger.tag > entry.tag
                         and younger.instruction.op == "ld"
                         and younger.address == entry.address and younger.mem_start is not None]
            if conflicts:
                first = min(conflicts, key=lambda item: item.tag)
                cpu.memory_replays += 1
                cpu.squash(first.tag, first.pc)
        return
    if instruction.branch:
        taken = (values[0] == values[1]) == (instruction.op == "beq")
        target = entry.pc + 1 + instruction.immediate
        actual = target if taken else entry.pc + 1
        cpu.btb[entry.pc % 8] = Prediction(entry.pc, target, taken)
        cpu.branches += 1
        if actual != entry.predicted_pc:
            cpu.mispredictions += 1
            cpu.squash(entry.tag + 1, actual)
    elif instruction.op == "addi":
        entry.result = values[0] + instruction.immediate
    elif instruction.op in ("add", "add.d"):
        entry.result = values[0] + values[1]
    elif instruction.op in ("sub", "sub.d"):
        entry.result = values[0] - values[1]
    else:
        entry.result = values[0] * values[1]
    entry.complete = cpu.cycle


def exe(cpu):
    for unit in ("integer", "fp_add", "fp_mul", "address"):
        config = getattr(cpu.config, unit)
        slots = config.count
        if unit in ("integer", "address"):
            slots -= sum(task.entry.instruction.unit == unit for task in cpu.executing)
        queue = cpu.lsq if unit == "address" else cpu.stations[unit]
        for entry in list(queue):
            # Store address generation does not wait for store data.
            operands = entry.operands[:1] if unit == "address" else entry.operands
            if (slots <= 0 or entry.ex_start is not None or entry.issue >= cpu.cycle
                    or not all(operand.ready(cpu.cycle) for operand in operands)):
                continue
            entry.ex_start = cpu.cycle
            cpu.executing.append(Execution(entry, cpu.cycle + config.latency - 1))
            if unit != "address":
                queue.remove(entry)
            slots -= 1
    for task in sorted(list(cpu.executing), key=lambda item: item.entry.tag):
        if task.entry.squashed is None and task.end == cpu.cycle:
            cpu.executing.remove(task)
            finish(cpu, task.entry)
