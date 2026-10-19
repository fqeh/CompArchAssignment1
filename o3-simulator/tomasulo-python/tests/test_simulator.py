"""Behavioral tests for input, timing, hazards, speculation, and all widths."""
from collections import Counter
from pathlib import Path
import random
import sys
import unittest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "code"))
from init import parse_program, read_program
from simulator import Simulator
from reference import interpret


class SimulatorTests(unittest.TestCase):
    def verify(self, program, width):
        expected_registers, expected_memory, expected_trace = interpret(program)
        result = Simulator(program, width).run(20000)
        self.assertEqual(result["registers"], expected_registers)
        self.assertEqual(result["memory"], expected_memory)
        committed = [r for r in result["instructions"] if r["status"] == "committed"]
        self.assertEqual([r["pc_bytes"] for r in committed], expected_trace)
        self.assertTrue(all(n <= width for n in Counter(r["issue"] for r in result["instructions"]).values()))
        self.assertTrue(all(n == 1 for n in Counter(r["wb"] for r in result["instructions"] if r["wb"]).values()))
        self.assertTrue(all(n == 1 for n in Counter(r["commit"] for r in committed).values()))
        self.assertEqual([r["commit"] for r in committed], sorted(r["commit"] for r in committed))
        for row in committed:
            self.assertLess(row["issue"], row["ex_start"])
            self.assertGreaterEqual(row["ex_end"], row["ex_start"])
            if row["wb"]:
                self.assertLess(row["ex_end"], row["wb"])
                self.assertLess(row["wb"], row["commit"])
            if row["instruction"]["op"] == "ld":
                self.assertLess(row["ex_end"], row["mem_start"])
                self.assertLess(row["mem_end"], row["wb"])
            if row["instruction"]["op"] == "sd":
                self.assertEqual(row["mem_end"], row["commit"])
                self.assertEqual(row["mem_start"], row["commit_start"])
        return result

    def run_text(self, text, width=4):
        return self.verify(parse_program(text), width)

    def test_input_defaults_and_all_widths(self):
        self.assertEqual(parse_program("Add R1 R0 R0").config.issue_width, 1)
        for width in range(1, 5):
            program = parse_program(f"iSSue   WIDTH = {width}\naddi r1, r0, 3 # comment")
            self.assertEqual(program.config.issue_width, width)
            self.assertEqual(self.verify(program, width)["registers"]["R1"], 3)

    def test_invalid_input(self):
        cases = ["Issue width = 0", "Issue width = 5", "Issue width = two",
                 "Issue width 2", "Issue width = 1\nIssue width = 2",
                 "ROB entries = 0", "Integer adder 2 0 1", "R0=1", "R32=2",
                 "R1=2.5", "Mem[2]=1", "Mem[256]=1", "Ld F2 0(R32)",
                 "Divide R1 R2 R3", "Beq R0 R0 20"]
        for text in cases:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_program(text)

    def test_parameter_table(self):
        p = parse_program("# of rs Cycles in EX Cycles in Mem # of FUs\n"
                          "Integer adder 4 2 2\nFP adder 5 6 2\n"
                          "FP multiplier 3 7 2\nLoad/store unit 8 3 5 2\nROB entries = 9")
        self.assertEqual((p.config.int_units, p.config.address_cycles, p.config.memory_cycles), (2, 3, 5))
        self.assertEqual(p.config.rob_entries, 9)

    def test_benchmarks_all_widths(self):
        for path in sorted((BASE / "benchmarks").glob("*.in")):
            for width in range(1, 5):
                with self.subTest(case=path.stem, width=width):
                    self.verify(read_program(path), width)

    def test_exact_basic_timing(self):
        result = self.run_text("Addi R1 R0 7", 1)
        r = result["instructions"][0]
        self.assertEqual((r["issue"], r["ex_start"], r["ex_end"], r["wb"], r["commit"]), (1, 2, 2, 3, 4))
        self.assertEqual(result["cycles"], 4)

    def test_same_cycle_raw_and_self_read(self):
        result = self.run_text("Integer adder 4 1 1\nAddi R1 R0 3\nAddi R1 R1 2\nAdd R2 R1 R1")
        a, b, c = result["instructions"]
        self.assertEqual([r["issue"] for r in (a, b, c)], [1, 1, 1])
        self.assertGreater(b["ex_start"], a["wb"])
        self.assertEqual(result["registers"]["R2"], 10)

    def test_no_skipping_structural_stall(self):
        result = self.run_text("Integer adder 1 4 1\nAddi R1 R0 1\nAddi R2 R0 2\n"
                               "Addi R3 R0 3\nAdd.d F1 F0 F0")
        rows = result["instructions"]
        self.assertGreaterEqual(rows[3]["issue"], rows[2]["issue"])
        self.assertGreater(rows[2]["issue"], rows[1]["issue"])
        self.assertGreater(result["statistics"]["issue_stall_cycles"], 0)

    def test_rob_capacity_one(self):
        result = self.run_text("ROB entries = 1\nAddi R1 R0 1\nAddi R2 R0 2\nAddi R3 R0 3")
        rows = result["instructions"]
        self.assertEqual(rows[1]["issue"], rows[0]["commit"])
        self.assertEqual(rows[2]["issue"], rows[1]["commit"])

    def test_war_and_waw(self):
        for width in range(1, 5):
            result = self.run_text("F1=2,F2=3,F4=4\nFP adder 8 2 1\nFP multiplier 8 10 1\n"
                                   "Add.d F3 F1 F2\nMult.d F1 F2 F4\n"
                                   "Mult.d F2 F4 F4\nAdd.d F2 F3 F3\nAdd.d F5 F2 F1", width)
            self.assertEqual(result["registers"]["F3"], 5)
            self.assertEqual(result["registers"]["F5"], 22)

    def test_integer_unpipelined_and_fp_pipelined(self):
        result = self.run_text("Integer adder 8 3 1\nFP adder 8 4 1\n"
                               "Add R1 R0 R0\nAdd R2 R0 R0\n"
                               "Add.d F1 F0 F0\nAdd.d F2 F0 F0")
        a, b, c, d = result["instructions"]
        self.assertGreater(b["ex_start"], a["ex_end"])
        self.assertEqual(d["ex_start"], c["ex_start"] + 1)
        self.assertLess(d["ex_start"], c["ex_end"])

    def test_multiple_functional_units_and_single_cdb(self):
        result = self.run_text("Integer adder 8 1 2\nAddi R1 R0 1\nAddi R2 R0 2")
        a, b = result["instructions"]
        self.assertEqual(a["ex_start"], b["ex_start"])
        self.assertEqual(b["wb"], a["wb"] + 1)

    def test_forwarding_nearest_matching_store(self):
        result = self.verify(read_program(BASE / "benchmarks/forwarding.in"), 4)
        loads = [r for r in result["instructions"] if r["instruction"]["op"] == "ld"]
        self.assertEqual([r["value"] for r in loads], [7, 11])
        self.assertTrue(all(r["mem_start"] == r["mem_end"] for r in loads))
        self.assertEqual(result["statistics"]["forwarded_loads"], 2)

    def test_load_waits_for_matching_store_data(self):
        result = self.run_text("Load/store unit 8 1 2 2\nF1=2,F2=3\n"
                               "Mult.d F4 F1 F2\nSd F4 0(R0)\nLd F6 0(R0)")
        self.assertEqual(result["registers"]["F6"], 6)
        self.assertGreater(result["instructions"][2]["mem_start"], result["instructions"][0]["wb"])

    def test_memory_replay(self):
        for width in range(1, 5):
            result = self.verify(read_program(BASE / "benchmarks/memory_replay.in"), width)
            self.assertGreater(result["statistics"]["memory_replays"], 0)
            self.assertEqual(result["registers"]["F6"], 18)
            self.assertTrue(any(r["squash_reason"] == "memory ordering replay" for r in result["instructions"]))

    def test_same_cycle_store_address_alias(self):
        # Store address becomes known as an earlier load would enter MEM.
        result = self.run_text("Integer adder 4 1 1\nLoad/store unit 8 1 1 2\n"
                               "F2=9,Mem[0]=1\nAddi R1 R0 0\nLd F8 4(R0)\n"
                               "Sd F2 0(R1)\nLd F4 0(R0)")
        self.assertEqual(result["registers"]["F4"], 9)

    def test_memory_single_port(self):
        result = self.run_text("Load/store unit 8 1 3 2\nMem[0]=1,Mem[4]=2,Mem[8]=3\n"
                               "Ld F1 0(R0)\nLd F2 4(R0)\nLd F3 8(R0)")
        rows = result["instructions"]
        self.assertTrue(all(b["mem_start"] > a["mem_end"] for a, b in zip(rows, rows[1:])))

    def test_branch_recovery_and_wrong_path_fault(self):
        result = self.verify(read_program(BASE / "benchmarks/branch_recovery.in"), 4)
        self.assertEqual(result["memory"]["0"], 3)
        self.assertEqual(result["registers"]["R1"], 0)
        first_branch = result["instructions"][0]
        target = next(r for r in result["instructions"] if r["pc_bytes"] == 16 and r["status"] == "committed")
        self.assertEqual(target["issue"], first_branch["ex_end"] + 2)

    def test_branch_loop_prediction(self):
        result = self.verify(read_program(BASE / "benchmarks/branch_loop.in"), 4)
        self.assertEqual(result["statistics"]["mispredictions"], 2)
        self.assertEqual(result["registers"]["R3"], 8)

    def test_branch_restores_surviving_register_mapping(self):
        result = self.run_text("Integer adder 8 3 2\nFP multiplier 8 12 1\nF1=2,F2=3\n"
                               "Mult.d F4 F1 F2\nBeq R0 R0 1\nAdd.d F4 F1 F1\nAdd.d F6 F4 F2")
        self.assertEqual(result["registers"]["F6"], 9)

    def test_real_fault_is_reported(self):
        for text in ("Ld F1 256(R0)", "Sd F1 -4(R0)", "Ld F1 2(R0)"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                Simulator(parse_program(text)).run()

    def test_btb_aliases_use_pc_tags(self):
        text = ("Integer adder 8 2 2\nR1=3\nAddi R1 R1 -1\nBne R1 R0 7\n"
                "Beq R0 R0 7\n" + "Addi R3 R0 99\n" * 6 + "Beq R0 R0 -10")
        for width in range(1, 5):
            result = self.run_text(text, width)
            self.assertEqual(result["registers"]["R3"], 0)

    def test_committed_mapping_survives_branch_recovery(self):
        result = self.run_text("Integer adder 8 4 2\nAddi R1 R0 7\n"
                               "Addi R2 R0 1\nBeq R2 R2 1\nAddi R1 R0 99\nAdd R3 R1 R1")
        self.assertEqual(result["registers"]["R3"], 14)

    def test_unknown_older_store_shadowed_by_newer_store(self):
        result = self.run_text("Integer adder 8 8 1\nLoad/store unit 8 1 2 2\n"
                               "F1=7,F2=9\nAddi R1 R0 0\nSd F1 0(R1)\n"
                               "Sd F2 0(R0)\nLd F4 0(R0)")
        self.assertEqual(result["registers"]["F4"], 9)
        self.assertEqual(result["statistics"]["memory_replays"], 0)

    def test_sample_cases_hand_calculated_values(self):
        for name, expected in (("sample_case_01", {"R1": 28, "F1": 5, "F2": 25, "F3": 0, "F4": 26}),
                               ("sample_case_02", {"R1": 24, "F1": 6, "F2": 36, "F3": 0, "F4": 37})):
            for width in range(1, 5):
                result = self.verify(read_program(BASE / f"benchmarks/{name}.in"), width)
                for register, value in expected.items():
                    self.assertEqual(result["registers"][register], value)

    def test_delayed_addresses_differential(self):
        for seed in range(30):
            rng = random.Random(1000 + seed)
            lines = ["Integer adder 8 5 2", "Load/store unit 8 2 2 2",
                     "FP multiplier 4 12 1", "ROB entries = 20", "F1=3,F2=7,Mem[0]=1"]
            for _ in range(12):
                address = rng.randrange(4) * 4
                lines.extend([f"Addi R1 R0 {address}", f"Sd F{rng.randint(1, 2)} 0(R1)",
                              f"Ld F3 {rng.randrange(4) * 4}(R0)", "Add.d F4 F3 F2"])
            for width in range(1, 5):
                with self.subTest(seed=seed, width=width):
                    self.verify(parse_program("\n".join(lines)), width)

    def test_r0_and_large_register_numbers(self):
        result = self.run_text("R31=4,F31=7\nAddi R0 R31 3\nSd F31 0(R31)\nLd F30 4(R0)")
        self.assertEqual(result["registers"]["R0"], 0)
        self.assertEqual(result["registers"]["F30"], 7)

    def test_empty_and_cycle_limit(self):
        result = Simulator(parse_program("")).run()
        self.assertEqual(result["cycles"], 0)
        with self.assertRaises(RuntimeError):
            Simulator(parse_program("Beq R0 R0 -1")).run(30)

    def test_randomized_differential_programs(self):
        for seed in range(60):
            rng = random.Random(seed)
            lines = [f"Integer adder {rng.randint(1, 5)} {rng.randint(1, 4)} {rng.randint(1, 2)}",
                     f"FP adder {rng.randint(1, 5)} {rng.randint(1, 5)} {rng.randint(1, 2)}",
                     f"FP multiplier {rng.randint(1, 4)} {rng.randint(2, 9)} {rng.randint(1, 2)}",
                     f"Load/store unit {rng.randint(1, 6)} {rng.randint(1, 3)} {rng.randint(1, 4)} {rng.randint(1, 2)}",
                     f"ROB entries = {rng.randint(1, 16)}",
                     "R1=1,R2=2,R3=3,F1=1,F2=2,F3=3,Mem[0]=1,Mem[4]=2"]
            for i in range(40):
                choice = rng.randrange(8)
                a, b, c = [rng.randint(1, 8) for _ in range(3)]
                if choice == 0:
                    lines.append(f"Addi R{a} R{b} {rng.randint(-4, 4)}")
                elif choice == 1:
                    lines.append(f"{rng.choice(['Add', 'Sub'])} R{a} R{b} R{c}")
                elif choice in (2, 3):
                    lines.append(f"{rng.choice(['Add.d', 'Sub.d', 'Mult.d'])} F{a} F{b} F{c}")
                elif choice == 4:
                    lines.append(f"Sd F{a} {rng.randrange(4) * 4}(R0)")
                elif choice == 5:
                    lines.append(f"Ld F{a} {rng.randrange(4) * 4}(R0)")
                elif choice == 6 and i < 38:
                    lines.append(f"{rng.choice(['Beq', 'Bne'])} R{b} R{c} {rng.randint(0, 2)}")
                else:
                    lines.append(f"Addi R{a} R0 {rng.randint(0, 3) * 4}")
            program = parse_program("\n".join(lines))
            for width in range(1, 5):
                with self.subTest(seed=seed, width=width):
                    self.verify(program, width)


if __name__ == "__main__":
    unittest.main(verbosity=2)
