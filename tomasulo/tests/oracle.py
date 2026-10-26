"""Independent sequential interpreter used only for verification.

Author: Ali Alfageeh.
This parser/interpreter does not import the simulator parser or pipeline logic.
It checks architectural results, not timing. Branch offsets are signed words.
Memory is a 256-byte array; Ld/Sd transfer little-endian IEEE binary32 values.
The .d ALU instructions retain Python floating-point arithmetic.
"""
from decimal import Decimal
import math
import re
import struct

OPS = {'ld','sd','beq','bne','add','addi','sub','add.d','sub.d','mult.d'}
NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'

def pack_float32(value):
    """Model single-precision storage independently using Python's struct."""
    try:
        return struct.pack('<f', value)
    except OverflowError:
        return struct.pack('<f', math.copysign(math.inf, value))

def same_number(actual, expected):
    """Compare exceptional values too; preserve the sign of floating zero."""
    if isinstance(actual, str) and actual in ('NaN','Infinity','-Infinity'):
        actual=float(actual)
    if math.isnan(expected):
        return math.isnan(actual)
    if actual != expected:
        return False
    return expected != 0 or math.copysign(1.0,actual)==math.copysign(1.0,expected)

def execute(text, max_steps=10000):
    registers = {f'{kind}{n}': 0 for kind in 'RF' for n in range(32)}
    memory = bytearray(256)
    memory_views = set(range(0, 256, 4))
    instructions = []
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].split('//', 1)[0].strip()
        if not line:
            continue
        if line.lower().split()[0] in OPS:
            instructions.append(re.split(r'[\s,]+', line))
            continue
        for address, value in re.findall(r'(?i)mem\s*\[\s*(\d+)\s*\]\s*=\s*('+NUMBER+r')', line):
            address=int(address)
            if not 0 <= address <= 252:
                raise ValueError('Invalid initial memory address in oracle')
            memory[address:address+4]=pack_float32(float(value))
            memory_views.add(address)
        for name, value in re.findall(r'(?i)\b([RF]\d+)\s*=\s*('+NUMBER+r')', line):
            registers[name.upper()] = int(Decimal(value)) if name.upper().startswith('R') else float(value)
    registers['R0'] = 0
    pc = steps = 0
    trace = []
    while 0 <= pc < len(instructions):
        if steps >= max_steps:
            raise RuntimeError('Sequential oracle exceeded step limit')
        ins = instructions[pc]
        op, args = ins[0].lower(), [a.upper() for a in ins[1:]]
        next_pc = pc + 1
        trace.append(pc)
        if op == 'addi':
            registers[args[0]] = registers[args[1]] + int(args[2])
        elif op in ('add', 'add.d', 'sub', 'sub.d', 'mult.d'):
            a, b = registers[args[1]], registers[args[2]]
            registers[args[0]] = a*b if op == 'mult.d' else a-b if op.startswith('sub') else a+b
        elif op in ('ld', 'sd'):
            match = re.fullmatch(r'(-?\d+)\((R\d+)\)', args[1])
            if not match:
                raise ValueError('Oracle cannot parse memory operand '+args[1])
            address = int(match.group(1)) + registers[match.group(2)]
            if not isinstance(address,int) or not 0 <= address <= 252:
                raise ValueError('Invalid memory address in oracle')
            if op == 'ld':
                registers[args[0]] = struct.unpack('<f', memory[address:address+4])[0]
            else:
                memory[address:address+4]=pack_float32(registers[args[0]])
                memory_views.add(address)
        else:
            equal = registers[args[0]] == registers[args[1]]
            taken = equal if op == 'beq' else not equal
            if taken:
                next_pc += int(args[2])
        registers['R0'] = 0
        pc = next_pc
        steps += 1
    views={str(a):struct.unpack('<f',memory[a:a+4])[0] for a in sorted(memory_views)}
    return {'registers': registers, 'memory': {a:v for a,v in views.items() if v != 0},
            'memory_bytes':list(memory),'committed': steps, 'trace': trace}
