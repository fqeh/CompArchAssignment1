"""In-order multiple issue. Assignment author: Ali Alfageeh."""
from simulator import Entry


def issue(sim):
    if sim.cycle < sim.fetch_after:
        return
    for _ in range(sim.width):
        if not 0 <= sim.pc < len(sim.program.instructions):
            break
        ins = sim.program.instructions[sim.pc]
        queue = sim.lsq if ins.unit == 'load_store' else sim.rs[ins.unit]
        capacity = getattr(sim.config, ins.unit).rs
        if len(sim.rob) >= sim.config.rob_entries or len(queue) >= capacity:
            sim.stats['structural_stalls'] += 1
            break  # Never bypass a blocked instruction in an issue bundle.
        # Capture sources before renaming destination, including within bundle.
        operands = [sim.source(register) for register in ins.sources]
        entry = Entry(sim.next_id, sim.pc, ins, sim.cycle, operands)
        sim.next_id += 1
        sim.rob.append(entry)
        sim.history.append(entry)
        queue.append(entry)
        sim.stats['issued'] += 1
        if ins.dest and ins.dest != 'R0':
            sim.rat[ins.dest] = entry.id
        next_pc = sim.pc + 1
        if ins.op in ('beq', 'bne'):
            prediction = sim.btb[sim.pc & 7]
            if prediction is not None and prediction['pc'] == sim.pc and prediction['taken']:
                next_pc = prediction['target']
            entry.predicted_next = next_pc
            sim.stats['branch_predictions'] += 1
        sim.pc = next_pc
