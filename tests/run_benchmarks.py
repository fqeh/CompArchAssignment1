#!/usr/bin/env python3
"""Reproduce width comparisons and save actual CLI output. Author: Ali Alfageeh."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from oracle import execute, same_number
OUT=ROOT/'results'

def main():
    OUT.mkdir(exist_ok=True)
    summary=[]
    for path in sorted((ROOT/'tests/benchmarks').glob('*.in')):
        text=path.read_text()
        expected=execute(text)
        baseline=None
        for width in range(1,5):
            dest=OUT/f'{path.stem}_w{width}'
            command=[sys.executable,str(ROOT/'code/main.py'),str(path),'--issue-width',str(width),'--json',str(dest.with_suffix('.json'))]
            completed=subprocess.run(command,capture_output=True,text=True,check=True)
            dest.with_suffix('.txt').write_text(completed.stdout)
            result=json.loads(dest.with_suffix('.json').read_text())
            for name,value in expected['registers'].items():
                assert same_number(result['registers'][name],value),(path,width,name)
            assert set(result['memory'])==set(expected['memory']),(path,width,'memory addresses')
            assert all(same_number(result['memory'][a],v) for a,v in expected['memory'].items()),(path,width,'memory views')
            assert result['memory_bytes']==expected['memory_bytes'],(path,width,'memory bytes')
            assert result['committed']==expected['committed'],(path,width,'committed')
            assert [r['pc'] for r in result['instructions'] if r['status']=='committed']==expected['trace'],(path,width,'control-flow')
            if baseline is None: baseline=result['cycles']
            summary.append({'benchmark':path.stem,'issue_width':width,'cycles':result['cycles'],
                'committed':result['committed'],'ipc':round(result['committed']/result['cycles'],4),
                'speedup_vs_width1':round(baseline/result['cycles'],4),
                'branch_mispredictions':result['stats']['branch_mispredictions'],
                'memory_replays':result['stats']['memory_replays'],
                'forwarded_loads':result['stats']['forwarded_loads'],
                'architectural_check':'PASS','input_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (OUT/'summary.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(summary[0]))
        writer.writeheader();writer.writerows(summary)
    print(f'PASS: {len(summary)} benchmark runs matched independent sequential architectural results.')
    print('Benchmark                  W1    W2    W3    W4')
    for name in sorted({r['benchmark'] for r in summary}):
        values=[r['cycles'] for r in summary if r['benchmark']==name]
        print(f'{name:26s}'+''.join(f'{n:6d}' for n in values))

if __name__=='__main__': main()
