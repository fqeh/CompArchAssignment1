"""Out-of-order execution with explicit completion cycles. Author: Ali Alfageeh."""
from init import validate_address


def exe(sim):
    # Completing jobs remain occupied through this cycle. Integer/address units
    # start a new operation only next cycle; FP pipes accept one per FU per cycle.
    old_jobs = list(sim.jobs)
    for job in sorted(old_jobs, key=lambda j: j['entry'].id):
        if job['end'] == sim.cycle and sim.active(job['entry']):
            complete(sim, job['entry'])
    for unit in ('integer', 'fp_add', 'fp_mul', 'load_store'):
        cfg = getattr(sim.config, unit)
        queue = sim.lsq if unit == 'load_store' else sim.rs[unit]
        if unit in ('integer', 'load_store'):
            occupied = sum(j['unit'] == unit and sim.active(j['entry']) and j['end'] >= sim.cycle
                           for j in old_jobs)
            slots = cfg.count - occupied
        else:
            slots = cfg.count
        for entry in list(queue):
            if slots <= 0:
                break
            if not sim.active(entry) or entry.ex or entry.issue >= sim.cycle:
                continue
            operands = entry.operands[:1] if unit == 'load_store' else entry.operands
            if not all(sim.ready(operand) for operand in operands):
                continue
            entry.ex = [sim.cycle, sim.cycle + cfg.ex - 1]
            job = dict(entry=entry, unit=unit, end=entry.ex[-1])
            sim.jobs.append(job)
            if unit != 'load_store':
                queue.remove(entry)
            slots -= 1
            if job['end'] == sim.cycle:
                complete(sim, entry)
    sim.jobs = [j for j in sim.jobs if j['end'] > sim.cycle and sim.active(j['entry'])]


def complete(sim, entry):
    ins = entry.ins
    values = [operand.value for operand in entry.operands]
    if ins.op in ('ld', 'sd'):
        address = values[0] + ins.immediate
        try:
            validate_address(address)
            entry.address = address
        except ValueError as exc:
            # A wrong-path fault is harmless if an older branch squashes it.
            entry.fault = str(exc)
            return
        if ins.op == 'sd':
            sim.check_memory_violation(entry)
    elif ins.op in ('beq', 'bne'):
        taken = (values[0] == values[1]) if ins.op == 'beq' else (values[0] != values[1])
        target = entry.pc + 1 + ins.immediate
        actual = target if taken else entry.pc + 1
        entry.resolved_at = sim.cycle
        sim.btb[entry.pc & 7] = dict(pc=entry.pc, taken=taken, target=target)
        if actual != entry.predicted_next:
            sim.stats['branch_mispredictions'] += 1
            sim.recover(entry.id + 1, actual, 'branch')
    else:
        if ins.op == 'addi':
            value = values[0] + ins.immediate
        elif ins.op in ('add', 'add.d'):
            value = values[0] + values[1]
        elif ins.op in ('sub', 'sub.d'):
            value = values[0] - values[1]
        else:
            value = values[0] * values[1]
        sim.queue_result(entry, value)
