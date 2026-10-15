import json
from pathlib import Path
import random
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tomasulo-python" / "code"))
from init import parse_text, read_program
from simulator import Simulator
from reference import execute


class SimulatorTests(unittest.TestCase):
    def simulate(self, text, width=4):
        return Simulator(parse_text(text), width).run(10000)

    def check_reference(self, program, width):
        cpu = Simulator(program, width).run(10000)
        registers, memory, trace = execute(program)
        self.assertEqual(cpu.registers, registers)
        self.assertEqual(cpu.memory, memory)
        self.assertEqual([e.pc for e in cpu.committed], trace)
        self.assertEqual(cpu.rat, {})
        self.assertEqual(cpu.lsq, [])
        self.assertEqual(cpu.executing, [])
        self.assertIsNone(cpu.memory_access)
        self.assertTrue(all(not queue for queue in cpu.stations.values()))
        commits = [e.commit for e in cpu.committed]
        self.assertEqual(commits, sorted(set(commits)))
        wb = [e.wb for e in cpu.history if e.wb is not None]
        self.assertEqual(len(wb), len(set(wb)))
        for cycle in range(1, cpu.cycle + 1):
            self.assertLessEqual(sum(e.issue == cycle for e in cpu.history), width)
        for e in cpu.committed:
            self.assertGreater(e.ex_start, e.issue)
            self.assertEqual(e.ex_end - e.ex_start + 1,
                             getattr(cpu.config, e.instruction.unit).latency)
            self.assertGreater(e.commit, e.ex_end)
            if e.wb is not None:
                self.assertGreater(e.wb, e.mem_end if e.mem_end is not None else e.ex_end)
                self.assertGreater(e.commit, e.wb)
            if e.mem_start is not None:
                self.assertGreater(e.mem_start, e.ex_end)
                self.assertEqual(e.mem_end - e.mem_start + 1,
                                 1 if e.forwarded else cpu.config.memory_latency)
        return cpu

    def test_hand_calculated_dependency_timing(self):
        cpu = self.simulate("Addi R1 R0 7\nAdd R2 R1 R1")
        first, second = cpu.committed
        self.assertEqual((first.issue, first.ex_start, first.wb, first.commit), (1, 2, 3, 4))
        self.assertEqual((second.issue, second.ex_start, second.wb, second.commit), (1, 4, 5, 6))
        self.assertEqual(cpu.registers["R2"], 14)

    def test_same_bundle_raw_waw_war_and_r0(self):
        program = parse_text("""
Integer adder 8 1 4
FP adder 8 2 2
FP multiplier 8 8 2
F1=2, F2=3, R1=8
Mult.d F3 F1 F2
Add.d F3 F1 F1
Add.d F4 F3 F2
Add R2 R1 R1
Addi R1 R0 5
Add R3 R2 R1
Addi R0 R0 99
Add R4 R0 R1
""")
        for width in range(1, 5):
            with self.subTest(width=width):
                cpu = self.check_reference(program, width)
                self.assertEqual(cpu.registers["F4"], 7)
                self.assertEqual(cpu.registers["R3"], 21)
                self.assertEqual(cpu.registers["R4"], 5)

    def test_structural_stall_cannot_skip_blocked_instruction(self):
        cpu = self.simulate("""
Integer adder 1 4 1
FP adder 4 2 1
Addi R1 R0 1
Addi R2 R0 2
Add.d F1 F0 F0
""")
        self.assertEqual([e.issue for e in cpu.committed], [1, 2, 2])
        self.assertGreater(cpu.issue_stalls, 0)

    def test_small_rob_lsq_and_repeated_writers(self):
        program = parse_text("""
ROB entries = 1
Load/store unit 1 2 3 1
F1=5
Sd F1 0(R0)
Ld F2 0(R0)
Add.d F2 F2 F1
Sd F2 4(R0)
Ld F2 4(R0)
Addi R1 R1 1
Addi R1 R1 1
""")
        for width in range(1, 5):
            with self.subTest(width=width):
                self.check_reference(program, width)

    def test_integer_unpipelined_fp_pipelined_and_multiple_units(self):
        cpu = self.simulate("""
Integer adder 8 3 1
FP adder 8 4 2
Addi R1 R0 1
Addi R2 R0 2
Add.d F1 F0 F0
Add.d F2 F0 F0
Add.d F3 F0 F0
""")
        rows = cpu.committed
        self.assertGreater(rows[1].ex_start, rows[0].ex_end)
        self.assertEqual(rows[2].ex_start, rows[3].ex_start)
        self.assertLess(rows[4].ex_start, rows[2].ex_end)

    def test_out_of_order_execution_and_in_order_commit(self):
        cpu = self.simulate("Mult.d F1 F0 F0\nAdd.d F2 F1 F1\nAddi R1 R0 9")
        self.assertLess(cpu.committed[2].ex_start, cpu.committed[1].ex_start)
        self.assertGreater(cpu.committed[2].commit, cpu.committed[1].commit)

    def test_forward_from_youngest_matching_store_not_nearest_store(self):
        cpu = self.simulate("""
Load/store unit 8 1 4 2
F1=7, F2=9
Mult.d F10 F1 F2
Sd F1 0(R0)
Sd F2 4(R0)
Ld F3 0(R0)
Sd F2 0(R0)
Ld F4 0(R0)
""")
        self.assertEqual(cpu.registers["F3"], 7)
        self.assertEqual(cpu.registers["F4"], 9)
        self.assertTrue(all(e.forwarded for e in cpu.committed if e.instruction.op == "ld"))

    def test_store_data_dependency(self):
        program = parse_text("""
Load/store unit 8 1 3 2
F1=2, F2=3
Mult.d F3 F1 F2
Sd F3 0(R0)
Ld F4 0(R0)
""")
        for width in range(1, 5):
            self.check_reference(program, width)

    def test_unknown_store_address_replays_completed_load(self):
        program = parse_text("""
Integer adder 8 8 1
Load/store unit 8 1 2 2
F1=9, Mem[0]=2
Addi R1 R0 0
Sd F1 0(R1)
Ld F2 0(R0)
Add.d F3 F2 F2
""")
        for width in range(1, 5):
            with self.subTest(width=width):
                cpu = self.check_reference(program, width)
                self.assertGreater(cpu.memory_replays, 0)
                self.assertEqual(cpu.registers["F3"], 18)

    def test_unknown_non_aliasing_store_allows_load(self):
        cpu = self.simulate("""
Integer adder 4 8 1
Load/store unit 4 1 2 2
F1=9, Mem[0]=2
Addi R1 R0 4
Sd F1 0(R1)
Ld F2 0(R0)
""")
        self.assertLess(cpu.committed[2].mem_start, cpu.committed[1].ex_end)
        self.assertEqual(cpu.memory_replays, 0)

    def test_single_port_and_store_only_at_rob_head(self):
        cpu = Simulator(parse_text("""
Load/store unit 8 1 4 4
Issue width = 4
F1=5
Mult.d F8 F1 F1
Sd F1 0(R0)
Ld F2 4(R0)
Ld F3 8(R0)
"""))
        while cpu.pc < len(cpu.program.instructions) or cpu.rob:
            if cpu.rob and cpu.rob[0].instruction.op == "mult.d":
                self.assertEqual(cpu.memory[0], 0)
            cpu.step()
        intervals = [set(range(e.mem_start, e.mem_end + 1)) for e in cpu.committed
                     if e.mem_start is not None]
        for i, interval in enumerate(intervals):
            for other in intervals[i + 1:]:
                self.assertFalse(interval & other)

    def test_branch_squash_recovers_rat_and_drops_store(self):
        program = parse_text("""
Integer adder 8 3 2
Load/store unit 8 1 2 2
F1=6
Addi R1 R0 4
Beq R0 R0 3
Addi R1 R0 99
Sd F1 0(R0)
Ld F2 256(R0)
Add R2 R1 R1
""")
        for width in range(1, 5):
            with self.subTest(width=width):
                cpu = self.check_reference(program, width)
                self.assertEqual(cpu.memory[0], 0)
                self.assertEqual(cpu.registers["R2"], 8)
                branch = cpu.committed[1]
                self.assertGreaterEqual(cpu.committed[2].issue, branch.ex_end + 2)
                self.assertTrue(any(e.squashed is not None for e in cpu.history))

    def test_loop_prediction_taken_and_not_taken_recovery(self):
        program = parse_text("""
Integer adder 8 1 2
R1=4
Addi R2 R2 1
Addi R1 R1 -1
Bne R1 R0 -3
Add R3 R2 R2
""")
        for width in range(1, 5):
            with self.subTest(width=width):
                cpu = self.check_reference(program, width)
                self.assertEqual(cpu.registers["R2"], 4)
                self.assertEqual(cpu.mispredictions, 2)
                self.assertEqual(cpu.btb[2].pc, 2)
                self.assertFalse(cpu.btb[2].taken)
                self.assertEqual(len(cpu.btb), 8)

    def test_btb_aliases_are_tagged(self):
        program = parse_text("""
Integer adder 8 1 2
R1=2
Beq R0 R0 1
Addi R7 R0 99
Addi R1 R1 -1
Addi R2 R2 1
Addi R3 R3 1
Addi R4 R4 1
Addi R5 R5 1
Addi R6 R6 1
Bne R1 R0 -9
""")
        for width in range(1, 5):
            cpu = self.check_reference(program, width)
            self.assertEqual(cpu.registers["R7"], 0)

    def test_precise_invalid_memory_faults(self):
        for op in ("Ld F1 2(R0)", "Sd F1 256(R0)", "Ld F1 -4(R0)"):
            with self.subTest(op=op), self.assertRaisesRegex(ValueError, "Invalid memory"):
                self.simulate(op)

    def test_empty_input_and_cycle_limit(self):
        self.assertEqual(self.simulate("").cycle, 0)
        with self.assertRaisesRegex(RuntimeError, "Exceeded"):
            Simulator(parse_text("Beq R0 R0 -1")).run(20)

    def test_case_insensitive_parser_defaults_and_errors(self):
        cpu = Simulator(parse_text("r10=4, f31=2.5\nmem[4]=7\nlD f2, 0(r10) # comment")).run()
        self.assertEqual(cpu.config.issue_width, 1)
        self.assertEqual(cpu.registers["F2"], 7)
        for text in ("Issue width = 0", "Issue width = 5", "ROB entries = 0",
                     "Integer adder 2 0 1", "FP adder 2 3", "Mem[2]=1",
                     "Mem[256]=1", "R0=1", "R32=2", "F2=nan",
                     "Addi F1 R0 1", "Add R1 R2", "Bne R1 R0 -2", "Wat R1"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_text(text)

    def test_benchmarks_all_widths(self):
        for path in sorted((ROOT / "benchmarks").glob("*.txt")):
            for width in range(1, 5):
                with self.subTest(benchmark=path.name, width=width):
                    self.check_reference(read_program(path), width)

    def test_randomized_differential(self):
        for seed in range(40):
            rng = random.Random(seed)
            header = [f"Integer adder {rng.randint(1, 8)} {rng.randint(1, 4)} {rng.randint(1, 3)}",
                      f"FP adder {rng.randint(1, 8)} {rng.randint(1, 5)} {rng.randint(1, 3)}",
                      f"FP multiplier {rng.randint(1, 6)} {rng.randint(2, 9)} {rng.randint(1, 2)}",
                      f"Load/store unit {rng.randint(1, 8)} {rng.randint(1, 3)} {rng.randint(1, 6)} {rng.randint(1, 3)}",
                      f"ROB entries = {rng.randint(1, 20)}", "F1=1, F2=2, F3=3, R1=4, R2=8"]
            instructions = []
            for index in range(50):
                op = rng.choice(["Addi", "Add", "Sub", "Add.d", "Sub.d", "Mult.d", "Ld", "Sd", "Beq", "Bne"])
                a, b, c = (rng.randint(0, 7) for _ in range(3))
                if op in ("Ld", "Sd"):
                    instructions.append(f"{op} F{a} {4 * rng.randrange(8)}(R0)")
                elif op == "Addi":
                    instructions.append(f"Addi R{a} R{b} {rng.randint(-8, 8)}")
                elif op in ("Beq", "Bne"):
                    instructions.append(f"{op} R{a} R{b} {rng.randint(0, min(3, 49 - index))}")
                else:
                    kind = "F" if "." in op else "R"
                    instructions.append(f"{op} {kind}{a} {kind}{b} {kind}{c}")
            program = parse_text("\n".join(header + instructions))
            for width in range(1, 5):
                with self.subTest(seed=seed, width=width):
                    self.check_reference(program, width)

    def test_cli_json_from_another_directory_and_bad_input(self):
        script = ROOT / "tomasulo-python" / "code" / "main.py"
        run = subprocess.run([sys.executable, str(script), "--json", "--issue-width", "2"],
                             cwd=ROOT.parent, text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["issue_width"], 2)
        legacy = subprocess.run([sys.executable, str(script), str(script.with_name("code.in")),
                                 "--json", "--issue-width", "2"],
                                cwd=ROOT.parent, text=True, capture_output=True)
        self.assertEqual(legacy.returncode, 0, legacy.stderr)
        self.assertEqual(json.loads(legacy.stdout), json.loads(run.stdout))
        bad = subprocess.run([sys.executable, str(script), "--issue-width", "5"],
                             text=True, capture_output=True)
        self.assertEqual(bad.returncode, 2)
        self.assertNotIn("Traceback", bad.stderr)


if __name__ == "__main__":
    unittest.main()
