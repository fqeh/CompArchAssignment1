"""Binary32 value checks using fixed IEEE 754 bit patterns."""
import math
from pathlib import Path
import re
import struct
import sys
import unittest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "code"))
from init import parse_program
from print_status import format_result
from simulator import Simulator


class Float32Tests(unittest.TestCase):
    def assert_bits(self, value, expected):
        # Equality to the decoded value also catches an unrounded binary64
        # number which would produce the expected bits only when packed here.
        decoded = struct.unpack("!f", expected.to_bytes(4, "big"))[0]
        self.assertEqual(value, decoded)
        self.assertEqual(struct.pack("!f", value), expected.to_bytes(4, "big"))

    def test_initial_values_and_ties_to_even(self):
        program = parse_program("R1=16777217,F1=0.1,F2=16777217,F3=16777219\n"
                                "Mem[0]=0.1,Mem[4]=-0.0,Mem[8]=-16777217")
        self.assertEqual(program.registers["R1"], 16777217)
        self.assert_bits(program.registers["F1"], 0x3DCCCCCD)
        self.assert_bits(program.registers["F2"], 0x4B800000)
        self.assert_bits(program.registers["F3"], 0x4B800002)
        self.assert_bits(program.memory[0], 0x3DCCCCCD)
        self.assert_bits(program.memory[4], 0x80000000)
        self.assert_bits(program.memory[8], 0xCB800000)

    def test_rounding_before_dependent_arithmetic_all_widths(self):
        program = parse_program(
            "FP adder 8 2 2\nFP multiplier 4 3 1\n"
            "F1=16777216,F2=1,F3=1.00000011920928955078125,F4=-1\n"
            "Add.d F5 F1 F2\nSub.d F6 F5 F1\nSub.d F7 F1 F4\n"
            "Mult.d F8 F3 F3\nSub.d F9 F8 F3\nAddi R1 R0 16777217")
        expected = {"F5": 0x4B800000, "F6": 0x00000000, "F7": 0x4B800000,
                    "F8": 0x3F800002, "F9": 0x34000000}
        for width in range(1, 5):
            with self.subTest(width=width):
                result = Simulator(program, width).run()
                for register, bits in expected.items():
                    self.assert_bits(result["registers"][register], bits)
                    row = next(row for row in result["instructions"]
                               if row["instruction"]["dest"] == register)
                    self.assert_bits(row["value"], bits)
                self.assertEqual(result["registers"]["R1"], 16777217)

    def test_load_store_and_forwarding_all_widths(self):
        program = parse_program(
            "FP multiplier 4 20 1\nLoad/store unit 8 1 2 2\n"
            "F1=0.1,F30=2,Mem[4]=16777219\n"
            "Mult.d F31 F30 F30\nSd F1 0(R0)\nLd F2 0(R0)\nLd F3 4(R0)")
        for width in range(1, 5):
            with self.subTest(width=width):
                result = Simulator(program, width).run()
                self.assert_bits(result["registers"]["F2"], 0x3DCCCCCD)
                self.assert_bits(result["registers"]["F3"], 0x4B800002)
                self.assert_bits(result["memory"]["0"], 0x3DCCCCCD)
                self.assertEqual(result["statistics"]["forwarded_loads"], 1)
                forwarded = result["instructions"][2]
                self.assertEqual(forwarded["mem_start"], forwarded["mem_end"])

    def test_overflow_subnormal_underflow_and_nan(self):
        program = parse_program(
            "FP multiplier 8 2 2\n"
            "F1=3.4028234663852886e38,F2=2,F3=1.1754943508222875e-38,F4=0.5\n"
            "F5=1.401298464324817e-45,F6=-1.401298464324817e-45\n"
            "Mult.d F7 F1 F2\nMult.d F8 F3 F4\nMult.d F9 F5 F4\n"
            "Mult.d F10 F6 F4\nSub.d F11 F7 F7")
        for width in range(1, 5):
            with self.subTest(width=width):
                result = Simulator(program, width).run()
                self.assert_bits(result["registers"]["F7"], 0x7F800000)
                self.assert_bits(result["registers"]["F8"], 0x00400000)
                self.assert_bits(result["registers"]["F9"], 0x00000000)
                self.assert_bits(result["registers"]["F10"], 0x80000000)
                self.assertTrue(math.isnan(result["registers"]["F11"]))

    def test_initial_values_must_fit_finite_binary32(self):
        for source in ("F1=3.5e38", "Mem[0]=-3.5e38"):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "finite in binary32"):
                parse_program(source)

    def test_console_preserves_distinct_binary32_values(self):
        result = Simulator(parse_program("F1=16777216,F2=16777218,F3=0.1\nMem[0]=0.1")).run()
        output = format_result(result)
        displayed = dict(re.findall(r"(F\d+)=(\S+)", output))
        self.assertEqual(displayed["F1"], "16777216")
        self.assertEqual(displayed["F2"], "16777218")
        self.assertEqual(displayed["F3"], "0.100000001")
        self.assertIn("0         0.100000001", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
