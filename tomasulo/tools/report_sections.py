"""Report content. Assignment author: Ali Alfageeh.

Executed by build_report.py with the formatting helpers in scope.
"""
summary=json.loads((ROOT/'results/summary.json').read_text())
test_log=(ROOT/'tests/test_results.txt').read_text()
test_count=int(re.search(r'Ran (\d+) tests',test_log)[1])
run_count=len(summary)
def result(name,width):
    return json.loads((ROOT/'results'/f'{name}_w{width}.json').read_text())

p('Tomasulo Algorithm<br/>Implementation', 'title')
p('<b>Ali Alfageeh</b><br/>Computer Architecture - Programming Assignment<br/>October 25, 2026')
p('GitHub repository: <link href="https://github.com/fqeh/CompArchAssignment1" color="#1f4e79">https://github.com/fqeh/CompArchAssignment1</link>', 'small')
STORY.append(Spacer(1,12))
heading('1  Introduction')
p('In this assignment, I extended a Python simulator of Tomasulo\'s algorithm to issue one, two, three, or four instructions per cycle. My goal was to compare how issue width affects performance while keeping the simulated program\'s results correct. I kept one common data bus and one in-order commit per cycle so that the comparison focuses on the effect of wider issue.')
p('I used reservation stations and register renaming to track dependencies and allow ready instructions to execute out of order. I used a reorder buffer to commit completed instructions in program order. I also made the processor configuration and initial register and memory values readable from an input file, so I could run different programs without editing the simulator.')
p('Main changes I made', 'h2')
p('I changed the issue stage to handle several instructions in the same cycle and corrected how dependencies and register mappings are tracked. I revised execution timing and resource handling so that instructions wait for their operands and use the functional units consistently.')
p('I added branch prediction and recovery so the simulator can continue issuing instructions before a branch is resolved and discard incorrect speculative work when needed. I also improved load and store handling, including forwarding, memory-order recovery, unaligned addresses, and single-precision memory transfers.')
p('I expanded the output to show each instruction\'s pipeline timing, the final register and memory values, and execution statistics. In the following sections, I explain the main code changes and compare measured results at each issue width.')
p('How I checked my implementation', 'h2')
p(f'I checked the final architectural state against an independent sequential interpreter and reviewed instruction timing and recovery behavior. My validation included {test_count} passing test methods, {run_count} benchmark runs, and 160 randomized comparisons. I also ran the two sample workloads at all four issue widths and included their timing tables in this report.')

change(1,'Configuration and issue-width input',
    'The starter reads only an instruction file and hardcodes processor state. The revised parser accepts the hardware table, ROB entries, register/memory initialization, and Issue width. The default is 1; values outside 1-4 are rejected. The command-line option can override the input.',
    ('original/tomasulo-python/code/main.py',"instructions = read_instruction",12),
    ('code/init.py',"match = re.fullmatch(r'(rob",14),
    'The snapshots show the original fixed setup and the new validated ROB/issue-width configuration block. Hardware-row parsing appears immediately above the modified excerpt.')

change(2,'In-order multiple issue',
    'The issue stage now repeats up to the configured width. It checks the ROB and the appropriate reservation station or load/store queue before each instruction. A structural hazard stops the bundle. Capturing each source before updating the destination mapping preserves dependencies between instructions issued in the same cycle.',
    ('original/tomasulo-python/code/issue.py','def issue(cycle',11),
    ('code/issue.py','def issue(sim):',22),
    'A blocked instruction is never skipped. Each successful issue updates the RAT before the next issue slot is considered. The branch-aware PC selection follows this excerpt.')

change(3,'Safe renaming and single-CDB write-back',
    'The original broadcast overwrites the register alias entry with a value even when a younger instruction has already renamed that register. The revision leaves the latest producer tag in the RAT and broadcasts only to operands waiting for the matching dynamic ID. Write-back chooses one eligible completed result per cycle.',
    ('original/tomasulo-python/code/wb.py','    # rat_int',8),
    ('code/wb.py','def wb(sim):',16),
    'An older WAW producer cannot erase a younger mapping. At commit, a mapping is removed only if its tag still equals the retiring entry ID. Sources from already-broadcast producers can be read from the ROB.')

change(4,'Execution timing and pipeline resources',
    'The starter advances functional-unit counters inside a routine that can be called twice in one cycle. I replaced incremental advancement with explicit inclusive start/end cycles. Ready instructions may bypass older blocked instructions in execution, but they cannot start in their issue cycle or consume a value broadcast during the same cycle.',
    ('original/tomasulo-python/code/exe.py','def fu_exe(',11),
    ('code/exe.py','            if not sim.active(entry)',14),
    'Each integer/address unit remains occupied through its completion cycle. Each FP unit can launch one operation per cycle. The shown end-cycle calculation prevents accidental double advancement.')

change(5,'Branch prediction at issue',
    'The starter stalls fetching on Bne and has no prediction. The new issue logic looks up an eight-entry tagged branch-target buffer using the least significant three bits of the word PC. An absent/mismatched entry predicts not taken; a taken hit redirects the next issue slot. Beq and Bne are both implemented.',
    ('original/tomasulo-python/code/issue.py','    # Bne ',14),
    ('code/issue.py','        next_pc = sim.pc + 1',8),
    'Prediction is recorded per dynamic branch. Resolution at the end of EX compares the actual next PC with this prediction and updates the BTB direction bit and target.')

change(6,'Misprediction recovery',
    'The starter changes the PC when a branch resolves, without speculative-state recovery. The new recovery path marks younger entries squashed, removes their reservation stations, queued results, executing jobs and memory requests, and rebuilds the RAT from the surviving ROB. Correct-path issue resumes at cycle n+2 after a misprediction resolved in n.',
    ('original/tomasulo-python/code/exe.py',"            elif (fu[0].op=='Bne'):",12),
    ('code/simulator.py','    def recover(',21),
    'Rebuilding mappings in surviving program order preserves the youngest valid writer to each register. Dynamic IDs are never reused, preventing old broadcasts from waking new instructions.')

change(7,'Load/store forwarding and speculative loads',
    'The original forwarding loop stops at the nearest store even when its address does not match. The revised memory stage selects the youngest older source for each of the four load bytes. It waits only for contributing store data. Full byte coverage forwards in one cycle; partial coverage is merged with memory at the configured latency. Loads can speculate past unresolved older store addresses.',
    ('original/tomasulo-python/code/mem.py','def forward_check_from_sd(',12),
    ('code/mem.py','def select_byte_sources(',13),
    'Forwarding and memory accesses share one serialized path. Per-byte source IDs remain in the ROB after load completion, allowing a later-discovered overlap to trigger replay without falsely replaying bytes hidden by newer stores.')

change(8,'Precise store commit and architectural updates',
    'The starter tests the truth value of a function object instead of calling the store-committable check. The replacement permits a store memory operation only when that store is the ROB head. It holds the port for the configured memory latency, writes memory on the final cycle, and then retires. An uncommitted wrong-path store cannot change architectural memory.',
    ('original/tomasulo-python/code/mem.py',"        if (ld_sd_queue[0].op=='Sd'):",10),
    ('code/commit.py','def commit(sim):',23),
    'Store MEM ranges represent commit-time memory access. Branches and stores have no CDB WB entry. One instruction commits per cycle; a register-writing instruction can commit only after its WB cycle.')

change(9,'Accepting byte address 18',
    'The previous version incorrectly required four-byte alignment. The assignment never states that restriction and its own example computes address 18 from R1=10 and Ld F4,8(R1). I removed the alignment requirement and replaced independent word entries with one shared 256-byte memory. Any four-byte start from 0 through 252 is valid; overlapping accesses observe the same bytes.',
    ('revision_before/init.py','def validate_address(address):',3),
    ('code/init.py','def validate_address(address):',3),
    'This comparison uses my earlier alignment check. Range checking remains: a four-byte access beginning at 253 would extend beyond byte 255.')
p('Shared-byte storage used by the revised version', 'h2')
snapshot('change_9_memory_after','code/init.py','    def __getitem__(self, address):',12,'AFTER')
p('The assignment does not specify endianness or extra unaligned latency. The model uses little-endian storage and the configured memory latency for every valid start address. Memory views are decoded from these shared bytes.', 'small')

change(10,'Single-precision memory transfers',
    'The previous version copied Python values directly into memory. The revised memory setter encodes each stored value as four binary32 bytes, and loads decode those bytes. Store-to-load forwarding uses the same encoding before merging bytes, so bypassing memory cannot bypass rounding. FP register initialization and .d arithmetic keep their existing precision because the assignment does not fully define their rounding rules.',
    ('revision_before/commit.py','        # Only the ROB head',3),
    ('code/init.py','def pack_float32(value):',15),
    'The shared memory setter in Figure 9 calls pack_float32; mem.py uses the same helper for forwarding. Stores round to nearest, ties to even; finite overflow becomes signed infinity. This replaces the previous limitation for loads/stores, without imposing binary32 arithmetic everywhere.')
p('Numerical regression', 'h2')
code_block('F1=16777217\nSd F1, 18(R0)\nLd F2, 18(R0)',9)
p('Expected and measured: F1 retains 16777217; F2 becomes 16777216 after the single-precision transfer. A forwarded load and a later memory load must return the same rounded value. Signed zero, subnormals, partial overlap and boundary accesses are covered by the updated tests.', 'small')

newpage()
heading('3  Results')
p('All results below were regenerated after the memory corrections. For each benchmark, widths 1, 2, 3 and 4 use identical instructions, hardware configuration and initial state. Only issue width changes. The independent sequential interpreter verifies final registers, decoded memory views, all 256 raw memory bytes, committed instruction count, and the committed PC sequence.')
p('3.1  Cycle-count comparison', 'h2')
rows=[['Benchmark','Width 1','Width 2','Width 3','Width 4','Check']]
for name in sorted({r['benchmark'] for r in summary}):
    items=sorted([r for r in summary if r['benchmark']==name],key=lambda r:r['issue_width'])
    rows.append([name]+[r['cycles'] for r in items]+['PASS'])
table(rows,[169,60,60,60,60,CONTENT-409],8,padding=3)
p('Interpretation', 'h2')
p('The rename-hazard workload improves from 25 to 20 cycles, a <b>1.25x speedup</b> (20% fewer cycles). Sample 02 improves from 47 to 46 cycles, approximately <b>1.022x</b>. Sample 01 remains at 36 cycles. Wider issue can expose ready work sooner, but it does not remove the single-CDB, in-order-commit, memory-port, or dependency bottlenecks.')
p('IPC = committed instructions / total cycles. Speedup = width-1 cycles / selected-width cycles. Squashed instructions consume resources and appear in the simulator output, but do not count as committed instructions. I used the same input program and initial state for all four widths in each comparison.')
p('Timing conventions', 'h2')
p('Stage processing order is COMMIT, WB, MEM, EX, ISSUE. EX and MEM intervals are inclusive; an interval such as 10-14 is five cycles. A dash denotes a stage not used. Readiness timestamps require consumers to start after the producing WB cycle. The following sample tables contain every committed instruction and use the same columns as the supplied report.')

for num,name in [(1,'sample_01'),(2,'sample_02')]:
    newpage()
    heading(f'3.{num+1}  Test case #{num:02d}')
    p('This workload and its configuration are transcribed from the supplied sample report. The timing results on the following pages were recomputed with this implementation.')
    text=(ROOT/'tests/benchmarks'/f'{name}.in').read_text()
    lines=[line for line in text.splitlines() if line.strip() and not line.startswith('#')]
    hardware=[]
    for line in lines[:4]:
        match=re.match(r'(Integer adder|FP adder|FP multiplier|Load/store unit)\s+(.*)',line)
        label,nums=match[1],match[2].split()
        hardware.append([label,nums[0],nums[1],nums[2] if label=='Load/store unit' else '-',nums[-1]])
    table([['Unit','RS','EX cycles','MEM cycles','FUs']]+hardware,[172,50,85,100,CONTENT-407])
    p(lines[4]+'; issue width varied from 1 through 4.','small')
    code_block('\n'.join(lines[5:7]),6.7)
    p('Instruction list', 'h2')
    code_block('\n'.join(lines[7:]),9)
    r=result(name,4)
    state=', '.join(f'{k}={r["registers"][k]:g}' for k in ['R1','R2','F1','F2','F3','F4','F20'])
    p('<b>Final state at every width:</b> '+state+'. R0 remains zero; all other registers are zero. Nonzero memory remains unchanged from the six initialized locations shown above.')
    if num==1:
        p('Manual check: the three loads access addresses 12, 20 and 28, whose values are 1, 0 and 5. Thus F4 = 1 squared + 0 squared + 5 squared = 26. F0 is zero, so the other product accumulation leaves F3 = 0.', 'small')
    else:
        p('Manual check: the accumulated squares are 1 squared and 6 squared, yielding F4 = 37. Final R1 is 24, F1 is 6, F2 is 36, and F3 is zero. Two load/store FUs provide two address units, while memory itself remains single-ported.', 'small')
    for pair in [(1,2),(3,4)]:
        newpage()
        heading(f'Test case #{num:02d}: widths {pair[0]} and {pair[1]}')
        for width in pair:
            timing(result(name,width),width)
        p(f'I measured these timings using {name}.in at issue widths {pair[0]} and {pair[1]}. EX/MEM are inclusive cycle ranges. All 17 instructions commit in program order.', 'caption')

newpage()
heading('4  Correctness and recovery evidence')
p(f'The regression suite contains <b>{test_count} passing unittest methods</b>. These include {run_count} benchmark/width combinations, 120 general randomized sequential-oracle comparisons (seed 20261025), and 40 additional overlapping-memory comparisons (seed 180032). The new tests also cover address 18, binary32 forwarding, byte-range replay and strict JSON output. Nested width checks are not separate unittest methods.')
table([
    ['Check','Evidence'],
    ['Same-cycle RAW','Dependent instructions issue together; consumer EX waits until after producer WB.'],
    ['WAW/WAR and R0','Hand-calculated rename benchmark and randomized register reuse; R0 always zero.'],
    ['Structural hazards','Full RS/ROB stops later issue slots; no younger instruction bypasses the stall.'],
    ['Resource timing','FP starts each cycle; integer EX is serialized; one CDB, one commit, one memory port.'],
    ['Branch prediction','Taken/not-taken paths, BTB collisions, nested redirects and exact n+2 refetch.'],
    ['Memory ordering','Youngest source per byte, partial overlaps, late store data and unknown-address replay.'],
    ['Memory compatibility','Address 18 and binary32 transfers, including rounded forwarding and exact raw-byte checks.'],
    ['Precise state','Wrong-path stores and completed results are squashed; invalid wrong-path accesses are harmless.'],
    ['Parser and compatibility','Invalid widths/addresses rejected; legacy starter byte offsets match the normalized input.'],
], [124,CONTENT-124],8)
p('Selected width-4 trace evidence', 'h2')
rr=result('memory_replay',4)
p(f'The memory-replay benchmark records {rr["stats"]["memory_replays"]} replay and finishes in {rr["cycles"]} cycles. The speculative load is present in the trace as squashed; a later dynamic instance commits the correct value.')
mini=[['ID','Instruction','EX','MEM','WB','COMMIT','Status']]
for row in rr['instructions']:
    mini.append([row['id'],row['text'],interval(row['ex']),interval(row['mem']),interval(row['wb']),interval(row['commit']),row['status']])
table(mini,[28,159,50,50,35,53,CONTENT-375],7)
p('The forwarding benchmark produces F3=7 and records one forwarded load; its MEM start equals its MEM end. The branch-squash benchmark finishes with R1=1, R2=7, R3=8 and Mem[0]=3; the speculative store of F1=9 and register writes of 99 are removed. I checked the dynamic instruction IDs and squash reasons in the simulator output to verify recovery.', 'small')

newpage()
heading('5  Reproduction and limitations')
p('Run the simulator and sample workloads', 'h2')
code_block('cd tomasulo\npython3 code/main.py\npython3 code/main.py inputs/sample_01.in --issue-width 4\npython3 code/main.py inputs/sample_02.in --issue-width 2 --json result.json',7.2)
p('Run these commands from the repository root. Python 3.10 or later is required; the simulator uses only the standard library. The default example in <b>code/code.in</b> sets issue width to 2. An input without an Issue width line defaults to 1. I included both sample inputs so their timing tables can be reproduced at widths 1 through 4.')
p('Compatibility decisions', 'h2')
p('I use word branch offsets: byte target = byte PC + 4 + 4 x offset. For older inputs that express offsets in bytes, I added <b>--legacy-branch-bytes</b>. For example, a byte offset of -12 corresponds to a word offset of -3. I also accept the assignment\'s unaligned load at address 18.')
p('Model limits and what is not implemented', 'h2')
p('No unresolved functional failure was observed in the supplied tests and documented extensions. Memory initialization, loads, stores and forwarding now use binary32 values; FP register initialization and .d arithmetic retain Python precision. Rounding-mode controls, FP status flags and fixed-width integer overflow are not modeled. There are no caches, OS services, interrupts or exception handlers. Invalid committing memory accesses raise an error; the configurable cycle limit stops infinite loops.')
p('The model fixes CDB width and commit width at one. Forwarding shares the single memory path. Reservation stations are freed at EX dispatch. Stores begin memory access only at the ROB head and commit at the end of that access. These choices are explicit so that timing comparisons can be reproduced. Branch prediction state is updated at EX resolution; speculative predictor updates are not rolled back, while architectural state is recovered.')
p('Readable memory output contains nonzero binary32 views at aligned starts and explicitly initialized or committed-store starts. Those views may overlap. JSON includes the authoritative 256-byte image in <b>memory_bytes</b>; nonfinite numbers are encoded as the strings NaN, Infinity or -Infinity. Little-endian storage and no extra unaligned-access latency are documented conventions.', 'small')
p('Repository contents', 'h2')
p('I organized the assignment under <b>tomasulo/</b>. I included the simulator in <b>code/</b>, the two report examples in <b>inputs/</b>, the verification suite in <b>tests/</b>, and saved traces and summaries in <b>results/</b>. I also included this PDF, its source in <b>tools/</b>, source snapshots in <b>report_assets/</b>, supplied materials in <b>original/</b>, earlier comparison files in <b>revision_before/</b>, the source diff, and attribution notes.')
p('References', 'h2')
p('[1] Supplied <i>programming-tomasulo.pdf</i>, four PDF pages: processor, ISA, input/output and report requirements.<br/>[2] Supplied <i>Sample_Tomasulo_Assignment_Report.pdf</i>, 21 PDF pages: report structure and Test Cases 01/02.<br/>[3] Supplied <i>tomasulo-python.zip</i>, original Python simulator, source headers attributed to Qing, May 2017.', 'small')
