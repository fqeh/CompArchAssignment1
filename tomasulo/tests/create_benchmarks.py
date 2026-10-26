"""Generate the documented regression workloads. Author: Ali Alfageeh."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent / 'benchmarks'
ROOT.mkdir(exist_ok=True)
DEFAULT = '''# Tomasulo benchmark. Author: Ali Alfageeh
# Unit             RS  EX  MEM FUs
Integer adder       8   1      1
FP adder            8   3      1
FP multiplier       8   8      1
Load/store unit     8   1   4  1
ROB entries = 32
'''
def write(name, program, initial='', config=DEFAULT, description=''):
    (ROOT / (name + '.in')).write_text(config + '\n# ' + description + '\n' + initial + '\n' + program.strip() + '\n')
INIT = 'R1=12, R2=32, F20=3.0\nMem[4]=3.0, Mem[8]=2.0, Mem[12]=1.0, Mem[24]=6.0, Mem[28]=5.0, Mem[32]=4.0\n'
write('sample_01', '''
Ld F1 0(R1)
Mult.d F2 F1 F0
Add.d F3 F3 F2
Mult.d F2 F1 F1
Add.d F4 F2 F4
Addi R1 R1 8
Ld F1 0(R1)
Mult.d F2 F1 F0
Add.d F3 F3 F2
Mult.d F2 F1 F1
Add.d F4 F2 F4
Addi R1 R1 8
Ld F1 0(R1)
Mult.d F2 F1 F0
Add.d F3 F3 F2
Mult.d F2 F1 F1
Add.d F4 F2 F4
''', INIT, '''# Sample report Test Case 01; transcribed inputs, not its timing outputs.
# Assignment implementation author: Ali Alfageeh
Integer adder   4  1     1
FP adder        4  3     1
FP multiplier   4  5     1
Load/store unit 4  1  6  1
ROB entries = 64
''', 'Exact sample workload 1; final R1=28,F1=5,F2=25,F3=0,F4=26.')
write('sample_02', '''
Ld F1 0(R1)
Mult.d F2 F1 F0
Add.d F3 F3 F2
Mult.d F2 F1 F1
Ld F1 0(R1)
Addi R1 R1 4
Add.d F4 F2 F4
Addi R1 R1 8
Ld F1 0(R1)
Mult.d F2 F1 F0
Add.d F3 F3 F2
Mult.d F2 F1 F1
Ld F1 0(R1)
Mult.d F2 F1 F0
Add.d F3 F3 F2
Mult.d F2 F1 F1
Add.d F4 F2 F4
''', INIT, '''# Sample report Test Case 02; transcribed inputs, not its timing outputs.
# Assignment implementation author: Ali Alfageeh
Integer adder   4  1      1
FP adder        3  3      2
FP multiplier   2  15     2
Load/store unit 4  1   5  2
ROB entries = 128
''', 'Exact sample workload 2; memory is still single-ported; final F4=37.')
LOOP = '''Ld F2 0(R1)
Mult.d F4 F2 F20
Ld F6 0(R2)
Add.d F6 F4 F6
Sd F6 0(R2)
Addi R1 R1 -4
Addi R2 R2 -4
Bne R1 R0 {offset}
Add.d F20 F2 F2'''
STARTER_CONFIG = '''# Starter workload with explicit configuration. Author: Ali Alfageeh
Integer adder   4 1     1
FP adder        3 4     1
FP multiplier   2 15    1
Load/store unit 5 1 5   1
ROB entries = 64
'''
write('starter_equivalent', LOOP.format(offset=-3), INIT, STARTER_CONFIG,
      'Original -12 BYTE displacement translated to -3 WORDS; loops pointer updates only.')
write('daxpy_loop', LOOP.format(offset=-8), INIT, STARTER_CONFIG,
      'Additional full-loop DAXPY benchmark; -8 words returns to first instruction.')
write('rename_hazards', '''
Addi R1 R0 5
Add R2 R1 R1
Addi R1 R0 9
Sub R3 R2 R1
Addi R0 R0 7
Add R4 R0 R3
Mult.d F1 F2 F3
Add.d F4 F1 F2
Add.d F1 F2 F2
Sub.d F5 F4 F1
''','F2=2,F3=3',description='Same-bundle RAW, WAW and WAR; R0 writes discarded.')
write('structural_stalls','''
Mult.d F1 F2 F3
Add.d F4 F1 F1
Add.d F5 F4 F4
Addi R1 R0 1
Add.d F6 F5 F5
Addi R2 R1 2
''','F2=2,F3=3', DEFAULT.replace('FP adder            8','FP adder            1').replace('ROB entries = 32','ROB entries = 3'),
      'Full FP RS blocks younger integer issue; ROB also fills.')
write('store_forwarding','''
Mult.d F10 F1 F2
Sd F1 0(R0)
Sd F2 0(R0)
Ld F3 0(R0)
Add.d F4 F3 F1
''','F1=2,F2=7,Mem[0]=99',description='Youngest matching older store must forward 7, not older store value 2.')
write('memory_replay','''
Addi R1 R0 4
Sd F1 0(R1)
Ld F2 4(R0)
Add.d F3 F2 F2
''','F1=7,Mem[4]=1',DEFAULT.replace('Integer adder       8   1','Integer adder       8  12').replace('Load/store unit     8   1   4','Load/store unit     8   1   1'),
      'Load initially bypasses older unresolved store; alias resolution must replay load and consumer.')
write('branch_squash','''
Addi R1 R0 1
Beq R1 R1 2
Sd F1 0(R0)
Addi R2 R0 99
Addi R2 R0 7
Bne R1 R0 1
Addi R3 R0 99
Add R3 R2 R1
''','F1=9,Mem[0]=3',description='Taken BEQ/BNE squash wrong-path store/register writes and recover RAT.')
write('btb_collision_loop','''
Addi R1 R0 3
Addi R2 R0 0
Beq R0 R0 1
Addi R9 R0 99
Addi R2 R2 1
Addi R8 R0 0
Addi R8 R0 0
Addi R8 R0 0
Addi R8 R0 0
Addi R1 R1 -1
Bne R1 R0 -9
Add R3 R1 R2
''',description='Branches at word PCs 2 and 10 alias BTB index 2; R2=3,R3=3,R9=0.')
write('parallel_fp','''
Mult.d F1 F20 F21
Add.d F2 F20 F21
Mult.d F3 F20 F22
Add.d F4 F21 F22
Mult.d F5 F21 F22
Add.d F6 F20 F22
Add.d F7 F1 F2
Add.d F8 F3 F4
Add.d F9 F5 F6
''','F20=2,F21=3,F22=4', DEFAULT.replace('FP adder            8   3      1','FP adder            8   3      2').replace('FP multiplier       8   8      1','FP multiplier       8   8      2'),
      'Two FP adders/multipliers exercise concurrent pipeline starts and CDB arbitration.')
write('case_and_boundaries','''
aDdI r31, r0, 252
sD f31, 0(r31)
lD f30, 0(r31)
sUb.D f29, f30, f1
aDd r30, r31, r0
''','r0=0,f31=4.5,f1=1.25',description='Case-insensitive commas, two-digit registers and last valid word address.')

# Follow-up: byte-addressed IEEE binary32 load/store behavior.
write('address18', '''
Add.d F1, F2, F3
Ld F4, 8(R1)
Sd F4, 22(R1)
Addi R3, R2, 1
''','R1=10,R2=20,F2=30.1\nMem[18]=16777217',description='Assignment-style effective byte address 10+8=18; finite straight-line example.')
write('byte_overlap', '''
Mult.d F30 F1 F2
Sd F1 18(R0)
Sd F2 20(R0)
Ld F3 18(R0)
Ld F4 20(R0)
Add.d F5 F3 F4
''','F1=1,F2=2',description='Overlapping binary32 stores merge bytes; F3=0,F4=2,F5=2.')
write('binary32_transfer', '''
Mult.d F30 F1 F2
Sd F1 18(R0)
Ld F3 18(R0)
Add.d F4 F1 F2
Ld F5 28(R0)
''','F1=16777217,F2=1\nMem[28]=16777217',description='Ld/Sd round16777217 to16777216, including forwarding; .d arithmetic retains precision.')
write('partial_overlap_replay', '''
Addi R1 R0 2
Sd F1 0(R1)
Sd F2 0(R0)
Ld F3 2(R0)
Add.d F4 F3 F3
''','F1=2,F2=1',DEFAULT.replace('Integer adder       8   1','Integer adder       8  12').replace('Load/store unit     8   1   4','Load/store unit     8   1   1'),
      'Newer store masks only2bytes; older unresolved store still requires replay for2other bytes.')
