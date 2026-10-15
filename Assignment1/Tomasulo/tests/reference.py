"""Independent sequential ISA oracle: no ROB, RAT, timing, or prediction."""


def execute(program, limit=10000):
    registers = dict(program.registers)
    memory = dict(program.memory)
    pc = 0
    trace = []
    while pc < len(program.instructions):
        if len(trace) >= limit:
            raise RuntimeError("Reference instruction limit exceeded")
        instruction = program.instructions[pc]
        trace.append(pc)
        next_pc = pc + 1
        op = instruction.op
        args = [registers[name] for name in instruction.sources]
        value = None
        if op == "ld":
            value = memory[args[0] + instruction.immediate]
        elif op == "sd":
            memory[args[0] + instruction.immediate] = args[1]
        elif op in ("beq", "bne"):
            condition = args[0] == args[1] if op == "beq" else args[0] != args[1]
            if condition:
                next_pc += instruction.immediate
        elif op == "addi":
            value = args[0] + instruction.immediate
        elif op in ("add", "add.d"):
            value = args[0] + args[1]
        elif op in ("sub", "sub.d"):
            value = args[0] - args[1]
        elif op == "mult.d":
            value = args[0] * args[1]
        if instruction.dest and instruction.dest != "R0":
            registers[instruction.dest] = value
        pc = next_pc
    return registers, memory, trace
