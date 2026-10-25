#!/usr/bin/env python3
"""Compare report controls with actual starter binaries. Author: Ali Alfageeh."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
rows=json.loads((ROOT/'results/benchmark_results.json').read_text())['runs']
with tempfile.TemporaryDirectory() as temp:
    work=Path(temp)
    for p in (ROOT/'baseline/src').iterdir():
        if p.is_file(): shutil.copy2(p,work/p.name)
    driver=(work/'predict.cc').read_text()
    (work/'predict_gshare.cc').write_text(driver.replace('new pm_predictor ()','new gshare_predictor ()'))
    for mode,source in [('always_taken','predict.cc'),('gshare','predict_gshare.cc')]:
        r=subprocess.run(['g++','-std=c++17','-O3','-w','-o',str(work/mode),str(work/source),str(work/'trace.cc')],text=True,capture_output=True)
        if r.returncode: raise RuntimeError(r.stderr)
    jobs=[r for r in rows if r['predictor'] in ('always_taken','gshare')]
    def compare(row):
        path=next((ROOT/'traces'/row['benchmark']).glob('*.trace.*'))
        r=subprocess.run([str(work/row['predictor']),str(path)],check=True,text=True,capture_output=True)
        actual=float(r.stdout.split()[0])
        expected=row['mpki']
        assert abs(actual-expected)<=0.00050001,(row,actual)
        return f"PASS {row['benchmark']:14s} {row['predictor']:12s} original={actual:.3f} MPKI"
    with ThreadPoolExecutor(max_workers=4) as pool:
        lines=list(pool.map(compare,jobs))
lines.append(f'{len(lines)} / {len(lines)} original-binary comparisons passed (3-decimal output).')
text='\n'.join(lines)+'\n'
(ROOT/'results/baseline_equivalence.txt').write_text(text)
print(text,end='')
