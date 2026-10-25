#!/usr/bin/env python3
"""Run all bundled traces with four predictors. Author: Ali Alfageeh."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MODES = ('always_taken','bimodal','gshare','pm')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--traces',type=Path,default=ROOT/'traces')
    parser.add_argument('--output',type=Path,default=ROOT/'results')
    parser.add_argument('--jobs',type=int,default=4)
    args=parser.parse_args()
    if args.jobs < 1: parser.error('--jobs must be positive')
    traces=sorted(args.traces.resolve().rglob('*.trace.*'))
    if not traces: parser.error('no *.trace.* inputs found')
    subprocess.run(['make','-C',str(ROOT/'src'),'predict'],check=True)
    jobs=[(path,mode) for path in traces for mode in MODES]
    def run(item):
        path,mode=item
        cmd=[str(ROOT/'src/predict'),str(path),'--predictor',mode,'--json']
        r=subprocess.run(cmd,text=True,capture_output=True,check=True)
        data=json.loads(r.stdout)
        data={'benchmark':path.parent.name,**data}
        assert data['direction_misses'] <= data['conditional_branches'] <= data['branches']
        if mode=='pm':
            assert data['global_hits']+data['global_misses']==data['conditional_branches']
        return data
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        rows=list(pool.map(run,jobs))
    for path in traces:
        selected=[r for r in rows if r['benchmark']==path.parent.name]
        assert len({(r['branches'],r['conditional_branches']) for r in selected})==1
    summary={}
    for mode in MODES:
        selected=[r for r in rows if r['predictor']==mode]
        misses=sum(r['direction_misses'] for r in selected)
        instructions=sum(r['instructions'] for r in selected)
        conditional=sum(r['conditional_branches'] for r in selected)
        summary[mode]={
            'traces':len(selected),'direction_misses':misses,
            'instructions':instructions,'conditional_branches':conditional,
            'mpki':1000*misses/instructions,
            'accuracy_percent':100*(1-misses/conditional) if conditional else 0,
            'global_hits':sum(r['global_hits'] for r in selected),
            'global_misses':sum(r['global_misses'] for r in selected),
            'global_replacements':sum(r['global_replacements'] for r in selected)}
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'benchmark_results.json').write_text(json.dumps({'runs':rows,'summary':summary},indent=2)+'\n')
    with (args.output/'benchmark_results.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    provenance={
        'author':'Ali Alfageeh','compiler':subprocess.check_output(['g++','--version'],text=True).splitlines()[0],
        'python':platform.python_version(),'platform':platform.platform(),
        'commands':['make -C src test','ASAN_OPTIONS=detect_leaks=0 make -C src sanitize','python3 scripts/benchmark.py --jobs 4','python3 tests/test_baseline_equivalence.py'],
        'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted([*ROOT.glob('src/*.h'),*ROOT.glob('src/*.cc'),*traces])}}
    (args.output/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    lines=['Predictor       Misses         MPKI        Accuracy']
    for mode,r in summary.items():
        lines.append(f"{mode:14s} {r['direction_misses']:12,d} {r['mpki']:11.6f} {r['accuracy_percent']:10.4f}%")
    lines.append(f'{len(rows)} complete runs; {len(traces)} traces; cold predictor for each run.')
    report='\n'.join(lines)+'\n'
    (args.output/'benchmark_summary.txt').write_text(report)
    print(report,end='')

if __name__=='__main__': main()
