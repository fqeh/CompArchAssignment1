"""Architectural and timing regression tests. Author: Ali Alfageeh."""
from collections import Counter
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
sys.path.insert(0, str(ROOT / 'tests'))
from init import parse_program
from simulator import Simulator
from oracle import execute, same_number

BENCHMARKS = sorted((ROOT / 'tests' / 'benchmarks').glob('*.in'))
CONFIG = '''Integer adder 8 1 1
FP adder 8 3 1
FP multiplier 8 6 1
Load/store unit 8 1 3 1
ROB entries = 32
'''

def simulate(text, width=None):
    return Simulator(parse_program(text), issue_width=width).run()

class SimulatorTests(unittest.TestCase):
    def assert_architecture(self, text, result):
        expected = execute(text)
        self.assertEqual(result['committed'], expected['committed'])
        self.assertEqual(set(result['registers']), set(expected['registers']))
        for name, value in expected['registers'].items():
            self.assertTrue(same_number(result['registers'][name], value), name)
        self.assertEqual(set(result['memory']), set(expected['memory']))
        for address, value in expected['memory'].items():
            self.assertTrue(same_number(result['memory'][address], value), 'Mem['+address+']')
        self.assertEqual(result['memory_bytes'], expected['memory_bytes'])
        committed = [r for r in result['instructions'] if r['status'] == 'committed']
        self.assertEqual([r['pc'] for r in committed], expected['trace'])

    def assert_pipeline(self, result, width):
        rows = result['instructions']
        self.assertTrue(all(n <= width for n in Counter(r['issue'] for r in rows).values()))
        self.assertTrue(all(n <= 1 for n in Counter(r['wb'] for r in rows if r['wb'] is not None).values()))
        self.assertTrue(all(n <= 1 for n in Counter(r['commit'] for r in rows if r['commit'] is not None).values()))
        committed = [r for r in rows if r['status'] == 'committed']
        self.assertEqual([r['commit'] for r in committed], sorted(r['commit'] for r in committed))
        for r in rows:
            if r['ex']:
                self.assertGreater(r['ex'][0], r['issue'])
                self.assertGreaterEqual(r['ex'][1], r['ex'][0])
            if r['mem']:
                self.assertGreater(r['mem'][0], r['ex'][1])
                self.assertGreaterEqual(r['mem'][1], r['mem'][0])
            if r['wb'] is not None:
                self.assertGreater(r['wb'], (r['mem'] or r['ex'])[1])
            if r['commit'] is not None:
                self.assertGreater(r['commit'], r['wb'] if r['wb'] is not None else r['ex'][1])
            else:
                self.assertEqual(r['status'], 'squashed')
        self.assertEqual(result['registers']['R0'], 0)
        if committed:
            self.assertEqual(result['cycles'], max(r['commit'] for r in committed))

    def test_all_benchmarks_all_widths(self):
        for path in BENCHMARKS:
            text = path.read_text()
            for width in range(1, 5):
                with self.subTest(benchmark=path.stem, width=width):
                    result = simulate(text, width)
                    self.assert_architecture(text, result)
                    self.assert_pipeline(result, width)

    def test_original_starter_legacy_byte_offset_compatibility(self):
        original=(ROOT/'tests/fixtures/starter_legacy.in').read_text()
        normalized=(ROOT/'tests/benchmarks/starter_equivalent.in').read_text()
        for width in range(1,5):
            with self.subTest(width=width):
                legacy=Simulator(parse_program(original,legacy_branch_bytes=True),issue_width=width).run()
                standard=simulate(normalized,width)
                self.assertEqual(legacy['registers'],standard['registers'])
                self.assertEqual(legacy['memory'],standard['memory'])
                self.assertEqual(legacy['cycles'],standard['cycles'])
                self.assertEqual(legacy['committed'],standard['committed'])
                self.assertEqual([r['pc'] for r in legacy['instructions'] if r['status']=='committed'],
                                 [r['pc'] for r in standard['instructions'] if r['status']=='committed'])

    def test_hand_calculated_architectural_answers(self):
        cases = {
            'sample_01': ({'R1':28,'F1':5,'F2':25,'F3':0,'F4':26}, {}),
            'sample_02': ({'R1':24,'F1':6,'F2':36,'F3':0,'F4':37}, {}),
            'rename_hazards': ({'R0':0,'R1':9,'R2':10,'R3':1,'R4':1,'F1':4,'F4':8,'F5':4}, {}),
            'daxpy_loop': ({'R1':0,'R2':20,'F2':3,'F20':6}, {'24':15,'28':11,'32':7}),
            'starter_equivalent': ({'R1':0,'R2':20,'F2':1,'F20':2}, {'24':6,'28':5,'32':7}),
            'branch_squash': ({'R1':1,'R2':7,'R3':8}, {'0':3}),
            'case_and_boundaries': ({'R30':252,'F30':4.5,'F29':3.25}, {'252':4.5}),
        }
        for name, (registers, memory) in cases.items():
            for width in range(1,5):
                with self.subTest(benchmark=name,width=width):
                    result=simulate((ROOT/'tests/benchmarks'/f'{name}.in').read_text(),width)
                    for register,value in registers.items():
                        self.assertEqual(result['registers'][register],value)
                    for address,value in memory.items():
                        self.assertEqual(result['memory'][address],value)

    def test_default_width_and_exact_single_instruction_timing(self):
        result = simulate('Addi R1 R0 5\n')
        row = result['instructions'][0]
        self.assertEqual([row['issue'], row['ex'], row['wb'], row['commit']], [1,[2,2],3,4])
        self.assertEqual(result['registers']['R1'], 5)

    def test_input_width_and_override(self):
        text = CONFIG + 'Issue width = 4\n' + '\n'.join(f'Addi R{i} R0 {i}' for i in range(1, 5))
        result = simulate(text)
        self.assertEqual([r['issue'] for r in result['instructions']], [1,1,1,1])
        result = simulate(text, 2)
        self.assertEqual([r['issue'] for r in result['instructions']], [1,1,2,2])

    def test_same_bundle_dependency_waits_until_after_writeback(self):
        result = simulate(CONFIG+'Addi R1 R0 3\nAdd R2 R1 R1\n', 4)
        producer, consumer = result['instructions']
        self.assertEqual(producer['issue'], consumer['issue'])
        self.assertGreater(consumer['ex'][0], producer['wb'])
        self.assertEqual(result['registers']['R2'], 6)

    def test_full_rs_blocks_younger_instruction_issue(self):
        text = (ROOT/'tests/benchmarks/structural_stalls.in').read_text()
        result = simulate(text, 4)
        rows = [r for r in result['instructions'] if r['status']=='committed']
        self.assertGreater(rows[2]['issue'], rows[1]['issue'])
        self.assertGreaterEqual(rows[3]['issue'], rows[2]['issue'])
        self.assertGreater(result['stats']['structural_stalls'], 0)

    def test_fp_pipeline_initiates_every_cycle(self):
        text = CONFIG+'F20=2,F21=3\n'+'\n'.join(f'Mult.d F{i} F20 F21' for i in range(1,5))
        result = simulate(text, 4)
        rows = result['instructions']
        self.assertEqual([r['ex'][0] for r in rows], [2,3,4,5])
        self.assertTrue(all(r['ex'][1]-r['ex'][0]+1 == 6 for r in rows))

    def test_integer_unit_is_not_pipelined(self):
        text = CONFIG.replace('Integer adder 8 1 1','Integer adder 8 3 1')+'Addi R1 R0 1\nAddi R2 R0 2\n'
        result = simulate(text, 4)
        first, second = result['instructions']
        self.assertEqual(first['ex'], [2,4])
        self.assertGreater(second['ex'][0], first['ex'][1])

    def test_two_fp_units_can_start_two_operations(self):
        text = CONFIG.replace('FP multiplier 8 6 1','FP multiplier 8 6 2')+'F20=2,F21=3\n'+'\n'.join(f'Mult.d F{i} F20 F21' for i in range(1,5))
        result = simulate(text, 4)
        self.assertEqual([r['ex'][0] for r in result['instructions']], [2,2,3,3])
        self.assertEqual(len({r['wb'] for r in result['instructions']}),4)

    def test_load_port_is_serialized(self):
        text = CONFIG.replace('Load/store unit 8 1 3 1','Load/store unit 8 1 3 2')+'Mem[0]=1,Mem[4]=2\nLd F1 0(R0)\nLd F2 4(R0)\n'
        rows = simulate(text,4)['instructions']
        self.assertEqual([r['ex'][0] for r in rows],[2,2])
        self.assertGreater(rows[1]['mem'][0], rows[0]['mem'][1])
        self.assertTrue(all(r['mem'][1]-r['mem'][0]+1==3 for r in rows))

    def test_youngest_store_forwards_in_one_cycle(self):
        result = simulate((ROOT/'tests/benchmarks/store_forwarding.in').read_text(),4)
        load = next(r for r in result['instructions'] if r['text'].lower().startswith('ld '))
        self.assertIsNotNone(load['forwarded_from'])
        self.assertEqual(load['mem'][0],load['mem'][1])
        self.assertEqual(result['registers']['F3'],7)

    def test_unknown_store_address_violation_replays(self):
        text = (ROOT/'tests/benchmarks/memory_replay.in').read_text()
        result = simulate(text,4)
        self.assertGreater(result['stats']['memory_replays'],0)
        self.assert_architecture(text,result)
        self.assertTrue(any(r['status']=='squashed' for r in result['instructions']))

    def test_branch_recovery_fetches_at_n_plus_two(self):
        text = CONFIG+'Beq R0 R0 1\nAddi R1 R0 99\nAddi R2 R0 7\n'
        result = simulate(text,1)
        branch = result['instructions'][0]
        target = next(r for r in result['instructions'] if r['pc']==2 and r['status']=='committed')
        self.assertEqual(target['issue'],branch['ex'][1]+2)
        self.assertEqual(result['registers']['R1'],0)
        self.assertEqual(result['registers']['R2'],7)

    def test_btb_collisions_preserve_control_flow(self):
        text = (ROOT/'tests/benchmarks/btb_collision_loop.in').read_text()
        result = simulate(text,4)
        self.assert_architecture(text,result)
        self.assertEqual(result['registers']['R2'],3)
        self.assertEqual(result['registers']['R9'],0)
        self.assertGreater(result['stats']['branch_mispredictions'],0)

    def test_invalid_config_and_operands_rejected(self):
        for text in ['Issue width = 0\nAddi R1 R0 1','Issue width = 5\nAddi R1 R0 1',
                     'ROB entries = 0\nAddi R1 R0 1','Addi R32 R0 1','Bogus R1 R0 1',
                     'Mem[253]=1\nLd F1 0(R0)','Mem[256]=1\nLd F1 0(R0)']:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_program(text)
        for width in [0,5]:
            with self.assertRaises(ValueError):
                simulate('Addi R1 R0 1',width)

    def test_deterministic_random_programs_against_oracle(self):
        rng = random.Random(20261025)
        for seed in range(30):
            lines=[CONFIG,'F1=1,F2=2,F3=3,F4=4','Mem[0]=5,Mem[4]=6,Mem[8]=7,Mem[12]=8']
            for _ in range(35):
                op=rng.choice(['add','addi','sub','add.d','sub.d','mult.d','ld','sd'])
                d,a,b=[rng.randrange(1,9) for _ in range(3)]
                if op=='addi': lines.append(f'Addi R{d} R{a} {rng.randrange(-5,6)}')
                elif op in ['add','sub']: lines.append(f'{op} R{d} R{a} R{b}')
                elif op in ['ld','sd']: lines.append(f'{op} F{d} {4*rng.randrange(4)}(R0)')
                else: lines.append(f'{op} F{d} F{a} F{b}')
            text='\n'.join(lines)
            for width in range(1,5):
                with self.subTest(seed=seed,width=width):
                    result=simulate(text,width)
                    self.assert_architecture(text,result)
                    self.assert_pipeline(result,width)

    def test_cli_runs_and_writes_json(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'result.json'
            completed=subprocess.run([sys.executable,str(ROOT/'code/main.py'),str(BENCHMARKS[0]),'--issue-width','4','--json',str(target)],text=True,capture_output=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            result=json.loads(target.read_text())
            self.assertEqual(result['registers']['R0'],0)
            self.assertIn('ISSUE',completed.stdout.upper())

if __name__ == '__main__':
    unittest.main(verbosity=2)
