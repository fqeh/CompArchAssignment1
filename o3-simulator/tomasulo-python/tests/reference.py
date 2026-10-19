"""Independent, sequential ISA interpreter used only as a correctness oracle."""
from ctypes import c_float
from init import check_address


def interpret(program, max_instructions=10000):
    registers = dict(program.registers)
    memory = dict(program.memory)
    pc = 0
    trace = []
    while pc < len(program.instructions):
        if len(trace) >= max_instructions:
            raise RuntimeError("reference instruction limit exceeded")
        ins = program.instructions[pc]
        values = [registers[source] for source in ins.sources]
        next_pc = pc + 1
        value = None
        if ins.op == "addi":
            value = values[0] + ins.immediate
        elif ins.op in ("add", "add.d"):
            value = values[0] + values[1]
        elif ins.op in ("sub", "sub.d"):
            value = values[0] - values[1]
        elif ins.op == "mult.d":
            value = values[0] * values[1]
        elif ins.op in ("ld", "sd"):
            address = values[0] + ins.immediate
            check_address(address)
            if ins.op == "ld":
                value = memory[address]
            else:
                memory[address] = c_float(values[1]).value
        elif ins.op in ("beq", "bne"):
            taken = values[0] == values[1]
            if ins.op == "bne":
                taken = not taken
            if taken:
                next_pc += ins.immediate
        else:
            raise AssertionError(f"oracle has no implementation for {ins.op}")
        if ins.dest and ins.dest != "R0":
            registers[ins.dest] = c_float(value).value if ins.dest.startswith("F") else value
        trace.append(pc * 4)
        pc = next_pc
    return registers, {str(a): v for a, v in memory.items() if v != 0}, trace
