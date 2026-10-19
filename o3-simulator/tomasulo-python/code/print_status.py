"""Human-readable output; full dynamic traces are also available as JSON."""


def interval(start, end):
    if start is None:
        return ""
    if end is None:
        return f"{start}-..."
    return str(start) if start == end else f"{start}-{end}"


def number(value):
    """Nine significant digits distinguish binary32 values in text output."""
    return format(value, ".9g") if isinstance(value, float) else str(value)


def format_result(result):
    lines = [f"Issue width: {result['config']['issue_width']}   Cycles: {result['cycles']}   "
             f"Committed: {result['statistics']['committed']}   IPC: {result['ipc']:.3f}", "",
             f"{'ID':<5} {'PC':<5} {'INSTRUCTION':<29} {'ISSUE':<7} {'EX':<11} "
             f"{'MEM':<11} {'WB':<7} {'COMMIT':<11} STATUS"]
    for row in result["instructions"]:
        committed = interval(row["commit_start"], row["commit"]) if row["commit_start"] else str(row["commit"] or "")
        status = row["status"]
        if status == "squashed":
            status += f" @{row['squash_cycle']} ({row['squash_reason']})"
        lines.append(f"{row['tag']:<5} {row['pc_bytes']:<5} {row['instruction']['text']:<29} "
                     f"{row['issue']:<7} {interval(row['ex_start'], row['ex_end']):<11} "
                     f"{interval(row['mem_start'], row['mem_end']):<11} "
                     f"{str(row['wb'] or ''):<7} {committed:<11} {status}")
    lines.extend(["", "REGISTER VALUES"])
    for kind in ("R", "F"):
        for start in range(0, 32, 8):
            lines.append("  ".join(f"{kind}{i}={number(result['registers'][f'{kind}{i}'])}"
                                   for i in range(start, start + 8)))
    lines.extend(["", "NON-ZERO MEMORY VALUES", "Address   Value"])
    lines.extend(f"{address:<9} {number(value)}" for address, value in result["memory"].items())
    if not result["memory"]:
        lines.append("(none)")
    lines.extend(["", "STATISTICS", "  ".join(f"{key}={value}" for key, value in result["statistics"].items())])
    return "\n".join(lines)
