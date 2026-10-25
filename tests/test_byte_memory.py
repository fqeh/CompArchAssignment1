"""Byte-addressed binary32 load/store regressions. Author: Ali Alfageeh.

Expected bytes use struct directly rather than the simulator's memory helper.
"""
import math
import json
import random
import subprocess
import tempfile
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
sys.path.insert(0,str(ROOT/'tests'))
from init import parse_program
from simulator import Simulator
from oracle import execute, same_number

HEADER='''Integer adder 12 1 1
FP adder 12 3 1
FP multiplier 12 16 1
Load/store unit 12 1 4 2
ROB entries = 48
'''
SLOW=HEADER.replace('Integer adder 12 1 1','Integer adder 12 12 1').replace('Load/store unit 12 1 4 2','Load/store unit 12 1 1 2')

class ByteMemoryTests(unittest.TestCase):
    def run_case(self,text,width=4):
        result=Simulator(parse_program(text),issue_width=width).run()
        expected=execute(text)
        self.assertEqual(result['memory_bytes'],expected['memory_bytes'])
        self.assertEqual(set(result['memory']),set(expected['memory']))
        for address,value in expected['memory'].items():
            self.assertTrue(same_number(result['memory'][address],value),f'Mem[{address}]')
        for register,value in expected['registers'].items():
            self.assertTrue(same_number(result['registers'][register],value),register)
        return result

    def test_assignment_example_effective_address18(self):
        text=(ROOT/'tests/benchmarks/address18.in').read_text()
        for width in range(1,5):
            with self.subTest(width=width):
                result=self.run_case(text,width)
                self.assertEqual(result['registers']['F4'],16777216)
                self.assertEqual(result['registers']['F1'],30.1)
                self.assertEqual(result['memory_bytes'][18:22],list(struct.pack('<f',16777216)))

    def test_all256bytes_and_last_valid_start252(self):
        for address in (0,1,2,3,18,249,250,251,252):
            with self.subTest(address=address):
                result=self.run_case(HEADER+f'F1=1.25\nSd F1 {address}(R0)\nLd F2 {address}(R0)\n')
                self.assertEqual(len(result['memory_bytes']),256)
                self.assertEqual(result['registers']['F2'],1.25)
                self.assertEqual(result['memory_bytes'][address:address+4],list(struct.pack('<f',1.25)))
        for address in (-1,253,254,255,256):
            for op in ('Ld F1','Sd F1'):
                with self.subTest(address=address,op=op):
                    with self.assertRaises(ValueError):
                        Simulator(parse_program(HEADER+f'{op} {address}(R0)\n')).run()
        for address in (253,254,255,256):
            with self.subTest(initializer=address):
                with self.assertRaises(ValueError):
                    parse_program(f'Mem[{address}]=1\n')

    def test_initializers_are_binary32_and_overlap_in_order(self):
        result=self.run_case(HEADER+'Mem[0]=3,Mem[2]=2,Mem[18]=16777217\nLd F1 0(R0)\nLd F2 2(R0)\nLd F3 18(R0)\n')
        self.assertEqual(result['registers']['F1'],0)
        self.assertEqual(result['registers']['F2'],2)
        self.assertEqual(result['registers']['F3'],16777216)
        self.assertEqual(result['memory_bytes'][:6],[0,0,0,0,0,64])

    def test_binary32_store_forwarding_rounds_before_load(self):
        text=(ROOT/'tests/benchmarks/binary32_transfer.in').read_text()
        for width in range(1,5):
            with self.subTest(width=width):
                result=self.run_case(text,width)
                self.assertEqual(result['registers']['F1'],16777217)
                self.assertEqual(result['registers']['F3'],16777216)
                load=next(r for r in result['instructions'] if r['pc']==2 and r['status']=='committed')
                self.assertIsNotNone(load['forwarded_from'])
                self.assertEqual(load['mem'][0],load['mem'][1])

    def test_double_precision_arithmetic_is_not_rounded_to_binary32(self):
        result=self.run_case(HEADER+'F1=16777217,F2=1\nAdd.d F3 F1 F2\nSub.d F4 F1 F2\nMult.d F5 F1 F2\n')
        self.assertEqual(result['registers']['F3'],16777218)
        self.assertEqual(result['registers']['F4'],16777216)
        self.assertEqual(result['registers']['F5'],16777217)

    def test_full_byte_coverage_from_two_stores_forwards(self):
        text=HEADER+'F1=1,F2=2\nMult.d F30 F1 F2\nSd F1 0(R0)\nSd F2 2(R0)\nLd F3 0(R0)\n'
        result=self.run_case(text)
        load=next(r for r in result['instructions'] if r['pc']==3)
        stores=[r for r in result['instructions'] if r['pc'] in (1,2)]
        self.assertEqual(load['byte_sources'],[stores[0]['id']]*2+[stores[1]['id']]*2)
        self.assertEqual(load['mem'][0],load['mem'][1])
        self.assertEqual(result['registers']['F3'],0)
        self.assertIsNone(load['forwarded_from'])

    def test_partial_byte_coverage_merges_with_memory(self):
        text=HEADER+'F1=1,F2=2,Mem[0]=3\nMult.d F30 F1 F2\nSd F2 2(R0)\nLd F3 0(R0)\n'
        result=self.run_case(text)
        load=next(r for r in result['instructions'] if r['pc']==2)
        store=next(r for r in result['instructions'] if r['pc']==1)
        self.assertEqual(load['byte_sources'],[0,0,store['id'],store['id']])
        self.assertEqual(load['mem'][1]-load['mem'][0]+1,4)
        self.assertEqual(result['registers']['F3'],0)

    def test_partial_overlap_waits_for_selected_store_data(self):
        text=HEADER+'F1=1,F2=2,Mem[0]=3\nMult.d F10 F1 F2\nSd F10 2(R0)\nLd F3 0(R0)\n'
        for width in range(1,5):
            with self.subTest(width=width):
                result=self.run_case(text,width)
                producer,store,load=result['instructions']
                self.assertGreater(load['mem'][0],producer['wb'])
                self.assertEqual(result['registers']['F3'],0)

    def test_unknown_partially_overlapping_store_causes_replay(self):
        text=SLOW+'F1=2,Mem[0]=3\nAddi R1 R0 2\nSd F1 0(R1)\nLd F2 0(R0)\nAdd.d F3 F2 F2\n'
        for width in range(1,5):
            with self.subTest(width=width):
                result=self.run_case(text,width)
                self.assertGreater(result['stats']['memory_replays'],0)
                self.assertEqual(result['registers']['F2'],0)
                self.assertEqual(result['registers']['F3'],0)

    def test_newer_store_masks_only_the_bytes_it_covers(self):
        text=(ROOT/'tests/benchmarks/partial_overlap_replay.in').read_text()
        expected=struct.unpack('<f',bytes([128,63,0,64]))[0]
        for width in range(1,5):
            with self.subTest(width=width):
                result=self.run_case(text,width)
                self.assertEqual(result['registers']['F3'],expected)
                self.assertEqual(expected,2.003875732421875)
                self.assertGreater(result['stats']['memory_replays'],0)

    def test_complete_newer_store_coverage_prevents_false_replay(self):
        text=SLOW+'F1=2,F2=1\nAddi R1 R0 2\nSd F1 0(R1)\nSd F2 0(R0)\nLd F3 0(R0)\n'
        for width in range(1,5):
            with self.subTest(width=width):
                result=self.run_case(text,width)
                self.assertEqual(result['registers']['F3'],1)
                self.assertEqual(result['stats']['memory_replays'],0)

    def test_cli_nonfinite_values_are_strict_json_strings(self):
        text=HEADER+'F1=1e40,F2=-1e40\nSd F1 18(R0)\nLd F3 18(R0)\nSd F2 24(R0)\nLd F4 24(R0)\nSub.d F5 F3 F3\n'
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'nonfinite.in';target=Path(d)/'nonfinite.json'
            source.write_text(text)
            completed=subprocess.run([sys.executable,str(ROOT/'code/main.py'),str(source),'--issue-width','4','--json',str(target)],capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            def reject_non_json_constant(value):
                raise AssertionError('Nonstandard numeric literal in JSON: '+value)
            saved=json.loads(target.read_text(),parse_constant=reject_non_json_constant)
            self.assertEqual(saved['registers']['F3'],'Infinity')
            self.assertEqual(saved['registers']['F4'],'-Infinity')
            self.assertEqual(saved['registers']['F5'],'NaN')

    def test_random_overlapping_accesses_against_byte_oracle(self):
        rng=random.Random(180032)
        for case in range(10):
            lines=[SLOW,'F1=1.1,F2=2.25,F3=-3.5,F4=16777217','Mem[0]=0.25,Mem[6]=1.75,Mem[18]=3.5']
            for _ in range(30):
                op=rng.choice(('addi','ld','sd','sd'))
                if op=='addi':
                    lines.append(f'Addi R1 R0 {rng.randrange(0,25)}')
                else:
                    register=rng.randrange(1,9)
                    operand='0(R1)' if rng.randrange(2) else f'{rng.randrange(0,29)}(R0)'
                    lines.append(f'{op} F{register} {operand}')
            text='\n'.join(lines)
            for width in range(1,5):
                with self.subTest(case=case,width=width):
                    self.run_case(text,width)

    def test_binary32_signedzero_subnormal_underflow_overflow(self):
        cases=[('-0.0',-0.0),('1.401298464324817e-45',2**-149),('1e-46',0.0),('1e39',math.inf),('-1e39',-math.inf)]
        for literal,expected in cases:
            with self.subTest(value=literal):
                text=HEADER+f'F1={literal}\nSd F1 18(R0)\nLd F2 18(R0)\n'
                result=self.run_case(text)
                self.assertTrue(same_number(result['registers']['F2'],expected))
                self.assertEqual(result['memory_bytes'][18:22],list(struct.pack('<f',expected)))

if __name__=='__main__':
    unittest.main(verbosity=2)
