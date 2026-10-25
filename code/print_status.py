"""Readable instruction timeline and final state. Author: Ali Alfageeh."""


def format_result(result):
    lines = [f"Tomasulo Simulator | Author: {result['author']}",
             f"Issue width: {result['issue_width']} | Cycles: {result['cycles']} | Committed: {result['committed']}", '',
             f"{'ID':>4} {'Instruction':<28} {'ISSUE':>5} {'EX':>9} {'MEM':>9} {'WB':>5} {'COMMIT':>6}  STATUS"]
    interval = lambda v: '-' if not v else f'{v[0]}-{v[-1]}'
    scalar = lambda v: '-' if v is None else str(v)
    for row in result['instructions']:
        status = row['status']
        if row['squash_reason']:
            status += ':' + row['squash_reason']
        lines.append(f"{row['id']:>4} {row['text']:<28} {row['issue']:>5} {interval(row['ex']):>9} {interval(row['mem']):>9} {scalar(row['wb']):>5} {scalar(row['commit']):>6}  {status}")
    lines += ['', 'REGISTER VALUES']
    for kind in ('R', 'F'):
        for start in range(0, 32, 8):
            lines.append('  '.join(f'{kind}{i}={result["registers"][f"{kind}{i}"]:g}' for i in range(start, start+8)))
    lines += ['', 'NON-ZERO MEMORY FLOAT VIEWS (byte starts; little-endian binary32)']
    lines += [f'Mem[{a}]={v:g}' for a, v in result['memory'].items()] or ['(none)']
    lines += ['', 'STATISTICS'] + [f'{key}: {value}' for key, value in result['stats'].items()]
    return '\n'.join(lines) + '\n'
