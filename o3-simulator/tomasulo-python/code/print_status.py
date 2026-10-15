"""Human-readable timing/state output and machine-readable results."""
from dataclasses import asdict


def span(start, end):
    if start is None:
        return "-"
    return str(start) if end == start else f"{start}-{end if end is not None else '?'}"


def as_result(cpu):
    return {
        "issue_width": cpu.config.issue_width,
        "cycles": cpu.cycle,
        "committed_instructions": len(cpu.committed),
        "branches_resolved": cpu.branches,
        "mispredictions": cpu.mispredictions,
        "memory_replays": cpu.memory_replays,
        "issue_stalls": cpu.issue_stalls,
        "registers": cpu.registers,
        "memory": {str(address): value for address, value in cpu.memory.items() if value != 0},
        "instructions": [{"id": e.tag, "pc": e.pc * 4, "instruction": e.instruction.text,
                          "issue": e.issue, "ex_start": e.ex_start, "ex_end": e.ex_end,
                          "mem_start": e.mem_start, "mem_end": e.mem_end, "wb": e.wb,
                          "commit": e.commit, "squashed": e.squashed, "forwarded": e.forwarded}
                         for e in cpu.history],
        "config": asdict(cpu.config),
    }


def format_result(cpu):
    lines = [f"Issue width: {cpu.config.issue_width}    Total cycles: {cpu.cycle}",
             f"{'ID':>4} {'PC':>4}  {'INSTRUCTION':<30} {'ISSUE':>5} {'EX':>9} {'MEM':>9} {'WB':>5} {'COMMIT':>6}  STATUS"]
    for e in cpu.history:
        status = f"squashed @{e.squashed}" if e.squashed is not None else "committed"
        if e.forwarded:
            status += " (forwarded)"
        lines.append(f"{e.tag:4} {4 * e.pc:4}  {e.instruction.text:<30} {e.issue:5} "
                     f"{span(e.ex_start, e.ex_end):>9} {span(e.mem_start, e.mem_end):>9} "
                     f"{str(e.wb) if e.wb else '-':>5} {str(e.commit) if e.commit else '-':>6}  {status}")
    lines.append("\nREGISTER VALUES")
    for kind in ("R", "F"):
        for start in range(0, 32, 8):
            names = [f"{kind}{i}" for i in range(start, start + 8)]
            lines.append(" ".join(f"{name:>10}" for name in names))
            lines.append(" ".join(f"{cpu.registers[name]:>10g}" for name in names))
    lines.extend(["\nNON-ZERO MEMORY VALUES", "Address (bytes)    Value"])
    lines.extend(f"{address:15}    {value:g}" for address, value in cpu.memory.items() if value != 0)
    lines.append(f"\nCommitted: {len(cpu.committed)}    Branch mispredictions: {cpu.mispredictions}"
                 f"    Memory replays: {cpu.memory_replays}")
    return "\n".join(lines) + "\n"
