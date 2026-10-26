"""Independent recovery and memory-order edge tests. Author: Ali Alfageeh."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
from init import parse_program
from simulator import Simulator

HEADER='''Integer adder 8 3 2
FP adder 8 3 2
FP multiplier 8 12 2
Load/store unit 12 1 2 2
ROB entries = 40
F1=2, F2=3, F3=4
Mem[0]=9, Mem[4]=7
'''
CASES={
 'youngest_matching_data_pending':('''Mult.d F30 F1 F2
Sd F1 0(R0)
Mult.d F9 F1 F2
Sd F9 0(R0)
Ld F10 0(R0)
''', {'F10':6}, {'0':6}),
 'nonmatching_store_does_not_obscure_match':('''Mult.d F30 F1 F2
Sd F1 0(R0)
Sd F2 4(R0)
Ld F10 0(R0)
''', {'F10':2}, {'0':2,'4':3}),
 'older_branch_squashes_younger_redirect':('''Addi R1 R0 1
Bne R1 R0 4
Beq R0 R0 6
Addi R7 R0 7
Ld F10 0(R0)
Addi R9 R0 9
Addi R2 R0 2
Beq R0 R0 2
Sd F1 0(R0)
Addi R8 R0 8
Addi R3 R0 3
''', {'R1':1,'R2':2,'R3':3,'R7':0,'R8':0,'R9':0,'F10':0}, {'0':9}),
 'wrong_path_pending_results':('''Addi R1 R0 1
Bne R1 R0 4
Mult.d F8 F1 F2
Add.d F9 F1 F2
Ld F10 0(R0)
Sd F3 4(R0)
Add.d F8 F2 F3
Add.d F9 F3 F3
''', {'F8':7,'F9':8,'F10':0}, {'4':7}),
}

class RecoveryEdgeTests(unittest.TestCase):
    def check_case(self, name):
        body, registers, memory = CASES[name]
        results = []
        for width in range(1, 5):
            with self.subTest(case=name, width=width):
                result = Simulator(parse_program(HEADER + body), issue_width=width).run()
                for register, expected in registers.items():
                    self.assertEqual(result['registers'][register], expected, register)
                for address, expected in memory.items():
                    self.assertEqual(result['memory'][address], expected, 'Mem[' + address + ']')
                results.append(result)
        return results

    def test_youngest_matching_store_waits_for_its_data(self):
        for result in self.check_case('youngest_matching_data_pending'):
            load = next(row for row in result['instructions'] if row['pc'] == 4)
            store = next(row for row in result['instructions'] if row['pc'] == 3)
            self.assertEqual(load['forwarded_from'], store['id'])

    def test_nonmatching_store_does_not_hide_older_match(self):
        for result in self.check_case('nonmatching_store_does_not_obscure_match'):
            load = next(row for row in result['instructions'] if row['pc'] == 3)
            store = next(row for row in result['instructions'] if row['pc'] == 1)
            self.assertEqual(load['forwarded_from'], store['id'])

    def test_older_branch_overrides_younger_redirect(self):
        for result in self.check_case('older_branch_squashes_younger_redirect'):
            self.assertGreaterEqual(result['stats']['branch_mispredictions'], 2)
            self.assertTrue(any(row['pc'] == 2 and row['status'] == 'squashed'
                                for row in result['instructions']))

    def test_squash_removes_active_and_completed_results(self):
        for result in self.check_case('wrong_path_pending_results'):
            squashed = [row for row in result['instructions'] if row['status'] == 'squashed']
            # Both an operation still executing and a result already broadcast
            # must disappear architecturally when the older branch redirects.
            self.assertTrue(any(row['wb'] is not None for row in squashed))
            self.assertTrue(any(row['text'].startswith('Mult.d') and row['ex']
                                and row['wb'] is None for row in squashed))
            self.assertTrue(all(row['commit'] is None for row in squashed))

    def test_wrong_path_invalid_memory_access_is_squashed(self):
        for instruction in ('Ld F9 253(R0)', 'Sd F3 256(R0)'):
            for width in range(1, 5):
                with self.subTest(instruction=instruction, width=width):
                    text = HEADER + ('Addi R1 R0 1\nBne R1 R0 1\n' + instruction +
                                     '\nAddi R2 R0 7\n')
                    simulator = Simulator(parse_program(text), issue_width=width)
                    result = simulator.run()
                    self.assertEqual(result['registers']['R2'], 7)
                    self.assertEqual(result['registers']['F9'], 0)
                    self.assertEqual(result['memory'], {'0': 9, '4': 7})
                    self.assertTrue(any(entry.fault and entry.status == 'squashed'
                                        for entry in simulator.history))

    def test_right_path_invalid_access_faults_precisely(self):
        for instruction in ('Ld F9 253(R0)', 'Sd F3 256(R0)'):
            for width in range(1, 5):
                with self.subTest(instruction=instruction, width=width):
                    text = HEADER + 'Addi R1 R0 1\n' + instruction + '\nAddi R2 R0 9\n'
                    simulator = Simulator(parse_program(text), issue_width=width)
                    with self.assertRaises(ValueError):
                        simulator.run()
                    self.assertEqual(simulator.regs['R1'], 1)
                    self.assertEqual(simulator.regs['R2'], 0)
                    self.assertEqual(simulator.regs['F9'], 0)
                    self.assertEqual(simulator.memory[0], 9)
                    self.assertEqual(simulator.memory[4], 7)

if __name__ == '__main__':
    unittest.main(verbosity=2)
