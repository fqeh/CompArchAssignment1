#!/usr/bin/env python3
"""End-to-end trace decoder / driver tests. Author: Ali Alfageeh."""
import bz2
import gzip
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / 'src/predict'

class DriverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.raw = b''.join(struct.pack('<BII', code, 0, 16)
                            for code in (0x14, 0x14, 0x24, 0x24, 0x30))
        self.path = self.root / "trace's input.raw"
        self.path.write_bytes(self.raw)

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, *args, path=None):
        return subprocess.run([str(EXE), str(path or self.path), *args],
                              text=True, capture_output=True)

    def result(self, mode='pm', path=None):
        result = self.call('--predictor', mode, '--json', '--instructions', '10', path=path)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_exact_direction_counts(self):
        for mode, misses in [('pm',3),('bimodal',3),('gshare',2),('always_taken',2)]:
            with self.subTest(mode=mode):
                r = self.result(mode)
                self.assertEqual(r['direction_misses'], misses)
                self.assertEqual(r['conditional_branches'], 4)
                self.assertEqual(r['branches'], 5)
                self.assertEqual(r['mpki'], misses * 100)
                self.assertEqual(r['accuracy_percent'], (4-misses)*25)

    def test_default_pm_and_original_output(self):
        r = self.call('--instructions','10')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, '300.000 MPKI\n')

    def test_compressed_and_plain_match(self):
        for suffix, compressor in [('.bz2',bz2.compress),('.gz',gzip.compress)]:
            path = self.root / ('compressed trace' + suffix)
            path.write_bytes(compressor(self.raw))
            for mode in ('pm','bimodal','gshare','always_taken'):
                self.assertEqual(self.result(mode,path), self.result(mode))

    def test_missing_file_fails(self):
        self.assertNotEqual(self.call(path=self.root/'missing').returncode,0)

    def test_invalid_cli_fails(self):
        cases = [('--predictor','unknown'),('--instructions','0'),
                 ('--instructions','-1'),('--instructions','5.5'),
                 ('--instructions',''),('--instructions','999999999999999999999'),
                 ('--predictor',),('--instructions',),('--unexpected',)]
        for args in cases:
            with self.subTest(args=args):
                self.assertNotEqual(self.call(*args).returncode,0)
        r = subprocess.run([str(EXE)], capture_output=True)
        self.assertNotEqual(r.returncode,0)

    def test_global_accounting(self):
        r = self.result()
        self.assertEqual(r['global_hits']+r['global_misses'],4)
        self.assertEqual(r['global_misses'],4)
        self.assertEqual(r['global_replacements'],2)

    def test_repeatability(self):
        self.assertEqual(self.result(),self.result())

    def test_corrupt_compression_fails(self):
        bad = self.root / 'bad.bz2'
        bad.write_bytes(b'BZ-not-a-bzip-stream')
        self.assertNotEqual(self.call(path=bad).returncode,0)

    def test_empty_trace_has_no_division_by_zero(self):
        empty = self.root / 'empty.raw'
        empty.write_bytes(b'')
        r = self.result(path=empty)
        self.assertEqual((r['branches'],r['direction_misses'],r['mpki']),(0,0,0))
        self.assertEqual(r['accuracy_percent'],0)

if __name__ == '__main__':
    unittest.main(verbosity=2)
