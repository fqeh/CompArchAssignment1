"""Tomasulo report using the supplied sample's three-section format."""
import ast
import json
import textwrap
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

PAGE_W, PAGE_H = 595, 842
LEFT, WIDTH = 107.775, 379.45
BOTTOM = 151
BODY = ParagraphStyle("SampleBody", fontName="Times-Roman", fontSize=11.6,
                      leading=14.1, alignment=TA_JUSTIFY, spaceAfter=9)
SMALL = ParagraphStyle("SampleSmall", parent=BODY, fontSize=9.5, leading=12, spaceAfter=8)
CAPTION = ParagraphStyle("SampleCaption", parent=BODY, alignment=TA_CENTER, fontSize=10.5)
CELL = ParagraphStyle("SampleCell", parent=SMALL, fontSize=8.5, leading=10.5, spaceAfter=0)
STARTER = json.loads(Path(__file__).with_name("tomasulo_starter_excerpts.json").read_text())


class SampleReport:
    def __init__(self, output):
        self.output = output
        self.pdf = canvas.Canvas(str(output), pagesize=(PAGE_W, PAGE_H), invariant=1,
                                 pageCompression=1)
        self.pdf.setTitle("Computer Architecture - Tomasulo Algorithm Implementation")
        self.pdf.setAuthor("Ali Alfageeh")
        self.pdf.setSubject("Introduction, Code Changes and Results")
        self.page, self.y = 0, 0

    def new_page(self, section, title=None, bookmark=None):
        if self.page:
            self.pdf.showPage()
        self.page += 1
        self.y = 674
        c = self.pdf
        c.setFont("Times-Roman", 11.6)
        c.drawString(LEFT, 709.7, "Computer Architecture")
        c.drawRightString(LEFT + WIDTH, 709.7, "Programming Assignment: Tomasulo")
        c.setLineWidth(1.5)
        c.line(LEFT, 704, LEFT + WIDTH, 704)
        c.setLineWidth(0.7)
        c.line(LEFT, 138, LEFT + WIDTH, 138)
        c.setFont("Times-Roman", 11)
        c.drawCentredString(PAGE_W / 2, 124, section.upper())
        c.drawRightString(LEFT + WIDTH, 124, f"Page {self.page}")
        if bookmark:
            c.bookmarkPage(bookmark)
            c.addOutlineEntry(title or bookmark, bookmark, level=0)
        if title:
            self.heading(title, 16.7)

    def reserve(self, amount):
        if self.y - amount < BOTTOM:
            raise ValueError(f"Tomasulo page {self.page} overflows by {BOTTOM - self.y + amount:.1f} pt")

    def heading(self, text, size=11.8):
        if stringWidth(text, "Times-Bold", size) > WIDTH:
            raise ValueError(f"Heading too wide: {text}")
        self.reserve(size + 13)
        self.pdf.setFont("Times-Bold", size)
        self.pdf.drawString(LEFT, self.y, text)
        self.y -= size + 13

    def p(self, text, style=BODY):
        item = Paragraph(text, style)
        _, height = item.wrap(WIDTH, 1200)
        self.reserve(height + style.spaceAfter)
        item.drawOn(self.pdf, LEFT, self.y - height + 3)
        self.y -= height + style.spaceAfter

    def bullet(self, text):
        self.p("&#8226; " + text)

    def code(self, text, size=8.6):
        text = textwrap.dedent(text).strip("\n")
        lines = text.splitlines()
        widest = max(stringWidth(line, "Courier", size) for line in lines)
        size = min(size, size * (WIDTH - 4) / max(widest, 1))
        if size < 7:
            raise ValueError(f"Code is too wide to read on page {self.page}: {widest}")
        leading = max(size * 1.2, 9.5)
        self.reserve(len(lines) * leading + 12)
        self.pdf.setFont("Courier", size)
        for line in lines:
            self.pdf.drawString(LEFT + 2, self.y - size, line)
            self.y -= leading
        self.y -= 12

    def table(self, rows, widths):
        if abs(sum(widths) - WIDTH) > 0.1:
            raise ValueError("Incorrect table width")
        content = [[Paragraph(("<b>" if i == 0 else "") + escape(str(value)) +
                              ("</b>" if i == 0 else ""), CELL) for value in row]
                   for i, row in enumerate(rows)]
        table = Table(content, colWidths=widths)
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.black),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        _, height = table.wrap(WIDTH, 1400)
        self.reserve(height + 13)
        table.drawOn(self.pdf, LEFT, self.y - height)
        self.y -= height + 13

    def timing_table(self, cpu):
        """Match the sample's plain monospaced, bracketed status table."""
        def single(value):
            return "[]" if value is None else f"[{value}]"

        def span(first, last):
            return "[]" if first is None else f"[{first}, {last}]"

        rows = [["", "ISSUE", "EXE", "MEM", "WB", "COMMIT"]]
        rows += [[e.instruction.text, single(e.issue), span(e.ex_start, e.ex_end),
                  span(e.mem_start, e.mem_end), single(e.wb), single(e.commit)]
                 for e in cpu.committed]
        positions = [0, 120, 160, 220, 280, 325]
        widths = [120, 40, 60, 60, 45, WIDTH - 325]
        self.reserve(len(rows) * 14.1 + 16)
        self.pdf.setFont("Courier", 9.3)
        for row in rows:
            for index, value in enumerate(row):
                if stringWidth(value, "Courier", 9.3) > widths[index] - 2:
                    raise ValueError(f"Timing cell too wide: {value}")
                self.pdf.drawString(LEFT + positions[index], self.y - 9.3, value)
            self.y -= 14.1
        self.y -= 16

    def initial(self, name):
        entry = STARTER[name]
        self.heading("Initial Version")
        self.p(f"{entry['file']}, supplied starter, lines {entry['first_line']}-{entry['last_line']} "
               "(excerpt).", SMALL)
        self.code(entry["text"])

    def save(self):
        self.pdf.save()
        print(f"Created {self.output}: {self.page} pages; 36 benchmark runs verified.")


def source(root, file, start, end=None):
    lines = (root / "tomasulo-python/code" / file).read_text().splitlines()
    first = next(i for i, line in enumerate(lines) if start in line)
    last = next((i for i in range(first + 1, len(lines)) if end and end in lines[i]), len(lines))
    return textwrap.dedent("\n".join(lines[first:last])).rstrip()


def function(root, file, name):
    code = (root / "tomasulo-python/code" / file).read_text()
    node = next(node for node in ast.walk(ast.parse(code))
                if isinstance(node, ast.FunctionDef) and node.name == name)
    return textwrap.dedent("\n".join(code.splitlines()[node.lineno - 1:node.end_lineno]))


def input_page(report, case, programs):
    stem = f"sample_report_{case:02}"
    program = programs[stem]
    report.new_page("3 Results", "3.1  TestCases" if case == 1 else None,
                    f"test-case-{case}")
    report.heading(f"3.1.{case}  Test Case #{case:02}", 13)
    report.heading("Configuration of the Architecture")
    cfg = program.config
    rows = [["", "# of rs", "Cycles in EX", "Cycles in Mem", "# of FUs"]]
    for label, unit in [("Integer adder", cfg.integer), ("FP adder", cfg.fp_add),
                        ("FP multiplier", cfg.fp_mul), ("Load/store unit", cfg.address)]:
        rows.append([label, unit.stations, unit.latency,
                     cfg.memory_latency if unit is cfg.address else "", unit.count])
    report.table(rows, [110, 42, 74, 95, WIDTH - 321])
    report.p(f"ROB entries = {cfg.rob_entries}<br/>R1=12, R2=32, F20=3.0<br/>"
             "Mem[4]=3.0, Mem[8]=2.0, Mem[12]=1.0, Mem[24]=6.0, Mem[28]=5.0, Mem[32]=4.0", SMALL)
    report.heading("List of Instructions")
    report.code("\n".join(ins.text for ins in program.instructions), 10)
    report.p(f"Input: benchmarks/{stem}.txt. The next four figures show issue widths 1, 2, 3 and 4.", SMALL)


def result_page(report, case, width, runs):
    cpu = runs[f"sample_report_{case:02}", width]
    figure = (case - 1) * 4 + width
    report.new_page("3 Results", bookmark=f"figure-{figure}")
    report.timing_table(cpu)
    report.p(f"Figure {figure}: Simulation results for Test-case #{case:02} "
             f"with Issue-width #{width:02}", CAPTION)
    report.p(f"Total cycles: {cpu.cycle}. All {len(cpu.committed)} instructions committed. "
             "EXE and MEM intervals include both endpoints; [] means that the stage does not apply.", SMALL)
    report.heading("Final Register and Memory Values")
    regs = ", ".join(f"{key}={value:g}" for key, value in cpu.registers.items() if value)
    mem = ", ".join(f"Mem[{key}]={value:g}" for key, value in cpu.memory.items() if value)
    report.p("<b>Registers:</b> " + regs + ".", SMALL)
    report.p("<b>Memory:</b> " + mem + ". All omitted values are zero.", SMALL)
    report.p(f"Checked against the sequential interpreter. Full output: "
             f"results/sample_report_{case:02}_w{width}.txt.", SMALL)


def build(root, programs, runs):
    r = SampleReport(root / "Tomasulo_Assignment_Report.pdf")
    r.new_page("1 Introduction", "1  Introduction", "introduction")
    r.p("<b>Tomasulo Algorithm.</b> Tomasulo's algorithm uses reservation stations, "
        "register renaming and result forwarding to execute ready instructions out of order. "
        "The reorder buffer keeps architectural updates in program order.")
    r.p("This assignment extends the supplied Python implementation to issue 1-4 "
        "instructions per cycle. The ISSUE, EX, MEM, WB and COMMIT module structure is retained.")
    r.bullet("Added a configurable issue width, dependency-safe renaming within each bundle "
             "and stalls when the next instruction has no free resources.")
    r.bullet("Tested both sample-report inputs and seven additional programs at all four widths, "
             "with timing and final-state checks.")
    r.heading("What Works")
    r.bullet("In-order multiple issue, out-of-order execution, precise retirement and all ten specified opcodes.")
    r.bullet("Pipelined FP units, configurable hardware, branch prediction/recovery, store forwarding and memory replay.")
    r.heading("Limitations")
    r.bullet("Writeback and retirement remain one instruction per cycle. Memory has one unpipelined port; "
             "extra load/store units add address calculators.")
    r.bullet("Python arithmetic does not model single-precision rounding or integer overflow. Caches, "
             "interrupts and general exception handlers are outside scope.")
    r.p("Ali Alfageeh | October 15, 2026. The sections and result figures follow the supplied "
        "sample; code and timings describe this implementation.", SMALL)

    r.new_page("2 Code Changes", "2  Code Changes", "code-changes")
    r.p("The changes below compare excerpts from the supplied starter with the submitted code. "
        "The starter's stage organization is kept, but state is now carried by the Simulator object.")
    r.p("<b>(1) Multiple issue in issue.py.</b> The input parser accepts issue widths 1-4, "
        "with a default of 1. Issue stops at the first full ROB or required queue.")
    r.initial("issue")
    r.heading("My Version")
    r.code(source(root, "issue.py", "def issue(cpu):", "        entry = Entry"), 8.1)
    r.p("A blocked instruction stops the bundle, so younger work cannot pass it. "
        "Instructions already issued during that cycle remain issued.", SMALL)

    r.new_page("2 Code Changes", "2.1  Source operands and renaming")
    r.p("The starter stores either a value or a tag in its RAT arrays. The revised version "
        "keeps the architectural registers separate and looks up the exact producer tag.")
    r.initial("renaming")
    r.heading("My Version")
    r.code(function(root, "issue.py", "source"), 8.2)
    r.p("Source operands are captured before the destination updates the RAT. This lets "
        "later instructions in the same bundle depend on earlier ones. Each instruction "
        "gets a new tag, so a reused register name cannot identify the wrong producer.", SMALL)

    r.new_page("2 Code Changes", "2.2  Writeback")
    r.p("The starter writes the broadcast value directly into the RAT entry for the "
        "destination register. If a younger instruction has renamed that register, "
        "an older completion must not erase its mapping.")
    r.initial("writeback")
    r.heading("My Version")
    r.code(function(root, "wb.py", "wb"), 8.1)
    r.p("Only consumers waiting for the selected dynamic tag receive the result. "
        "The single CDB broadcasts at most one eligible result per cycle, as specified "
        "in the handout. Issue width does not increase the writeback width.", SMALL)

    r.new_page("2 Code Changes", "2.3  Commit")
    r.p("Only the head of the ROB may update architectural state. The revised retirement "
        "helper removes a RAT entry only if it still names the retiring instruction.")
    r.initial("commit")
    r.heading("My Version")
    r.code(function(root, "commit.py", "retire"), 8.4)
    r.p("The commit stage checks that a register-producing instruction wrote back in "
        "an earlier cycle. A store starts its memory transfer only at the ROB head, "
        "with both address and data ready; memory changes on its final transfer cycle. "
        "At most one instruction retires per cycle.", SMALL)
    r.p("This prevents a wrong-path store from updating memory before an older unresolved branch.", SMALL)

    r.new_page("2 Code Changes", "2.4  Execution cycle accounting")
    r.p("In the starter, fu_exe increments an operation's counter whenever it is called. "
        "The scheduler can call it again after accepting waiting work in the same cycle. "
        "The revised code records an explicit completion cycle instead.")
    r.initial("cycles")
    r.heading("My Version")
    r.p("exe.py, scheduling and completion excerpts:", SMALL)
    r.code(source(root, "exe.py", "            entry.ex_start =", '            if unit != "address":'), 8.4)
    r.code(source(root, "exe.py", "    for task in sorted"), 8.3)
    r.p("An operation that begins in cycle n with latency L finishes in n+L-1. "
        "A one-cycle operation therefore begins and ends in the same EX cycle. "
        "It cannot start in its issue cycle or write back in its completion cycle.")

    r.new_page("2 Code Changes", "2.5  Selecting ready instructions")
    r.p("The starter scans reservation stations for ready operands. The revised scheduler "
        "also checks cycle timestamps and available functional units.")
    r.initial("ready")
    r.heading("My Version")
    r.code(source(root, "exe.py", "        for entry in list(queue):", "            entry.ex_start ="), 8.2)
    r.p("Entries remain in issue order within each queue. The scheduler selects the "
        "oldest ready work for that unit, while a blocked older instruction may wait. "
        "Execution can therefore be out of order even though issue and retirement are in order.")
    r.p("Integer and address units remain occupied until completion. FP add and multiply "
        "units are pipelined and can accept new work each cycle, up to their configured count.")

    r.new_page("2 Code Changes", "2.6  Load/store ordering")
    r.p("The starter's forwarding search stops at the nearest older store. The revised "
        "search selects the youngest older store at the same address, even when a "
        "nonmatching store lies between it and the load.")
    r.initial("memory")
    r.heading("My Version")
    r.code(source(root, "mem.py", "            stores =", "            entry.mem_start ="), 8.1)
    r.p("The load waits if the matching store's data is unavailable. Forwarding takes "
        "one cycle; other accesses use the configured memory latency. The memory port "
        "is single-ported and unpipelined, and a load leaves the queue when its value returns.")
    r.p("Loads may pass stores with unknown addresses. When an older store resolves "
        "to an address already read by a younger load, that load and all younger work "
        "are replayed. The check includes loads still in the ROB after leaving the queue.", SMALL)

    r.new_page("2 Code Changes", "2.7  Order of pipeline stages")
    r.p("The stage calls run in reverse order so a result from a later stage is not "
        "used too early by a preceding stage during the same cycle.")
    r.heading("Initial Version")
    r.p("main.py call order, with arguments omitted:", SMALL)
    r.code("issue(...)\nexe(...)\nmem(...)\nwb(...)\ncommit(...)", 10)
    r.heading("My Version")
    r.p("simulator.py:", SMALL)
    r.code(function(root, "simulator.py", "step"), 10)
    r.p("Timestamps provide a second check. A consumer cannot execute in the cycle "
        "its producer broadcasts. For Addi R1 R0 7 followed by Add R2 R1 R1 at width 2, "
        "both issue in cycle 1. The first executes in 2 and broadcasts in 3; the second "
        "executes in 4 and broadcasts in 5. They commit in cycles 4 and 6, leaving R2=14.")

    r.new_page("2 Code Changes", "2.8  Branch recovery")
    r.p("The starter waits for its Bne handling to make the PC valid again. The revised "
        "version predicts during issue and resolves both Beq and Bne in EX.")
    r.initial("branch")
    r.heading("My Version")
    r.code(source(root, "exe.py", "    if instruction.branch:", "    elif instruction.op"), 8.2)
    r.p("An eight-entry tagged BTB uses the low three bits of the word PC and a "
        "one-bit prediction. A mismatch squashes younger ROB entries, reservation stations, "
        "memory work and executing instructions. The RAT is rebuilt from surviving writers, "
        "and correct fetch resumes in cycle n+2 after resolution in n.", SMALL)
    r.p("Branch offsets are signed words: byte target = PC + 4 + offset * 4. "
        "The eight-instruction vector loop uses -8 to return to its first instruction; "
        "the starter's legacy -12 immediate was corrected for this convention.", SMALL)

    r.new_page("3 Results", "3  Results", "results")
    r.p("The next pages use the sample report's two hardware configurations and "
        "instruction lists. Each case is followed by four separate simulation figures, "
        "one for each issue width. These are fresh results from the submitted simulator.")
    rows = [["Benchmark", "W1", "W2", "W3", "W4"]]
    for name in sorted(programs):
        rows.append([name, *[runs[name, width].cycle for width in range(1, 5)]])
    r.table(rows, [WIDTH - 156, 39, 39, 39, 39])
    r.p("The values are simulated cycles. All 36 runs match a separate sequential "
        "interpreter in registers, memory and committed instruction sequence.", SMALL)
    r.p("The sample report widens writeback and retirement and allows different memory "
        "concurrency. This implementation keeps one CDB, one memory port and one retirement "
        "per cycle, so its results differ. Sample case 01 takes 36 cycles at every width; "
        "case 02 takes 47 cycles at width 1 and 46 at widths 2-4.")
    r.p("Wider issue helps when it reaches ready work sooner. The late-critical-path "
        "program improves from 27 to 21 cycles. Dependencies, memory serialization and "
        "retirement still limit the other programs.", SMALL)

    for case in (1, 2):
        input_page(r, case, programs)
        for width in range(1, 5):
            result_page(r, case, width, runs)

    r.new_page("3 Results", "3.2  Additional Tests", "additional-tests")
    r.p("The following seven programs cover hazards and recovery that are not present "
        "in the two supplied sample streams. Each runs at widths 1, 2, 3 and 4.")
    r.table([["Test", "Purpose and selected final values"],
             ["branches", "Loop recovery and wrong-path stores; R2=4, R3=8; memory stays zero"],
             ["dependencies", "RAW/WAR/WAW and R0; F3=4, F4=7, R3=21, R0=0"],
             ["independent", "Mixed ready operations; F3=6, F7=9, F10=6, R4=4"],
             ["late_critical_path", "Late multiply/add chain; F3=6, F4=12"],
             ["memory", "Replay and forwarding; F3=9, F4=18; Mem[0]=9, Mem[4]=7, Mem[8]=9"],
             ["structural", "Two-entry ROB and small queues; F7=16, Mem[0]=8"],
             ["vector_loop", "Three iterations; R1=0; Mem[24]=15, Mem[28]=11, Mem[32]=7"]],
            [110, WIDTH - 110])
    r.p("The 20 unittest tests include hand-checked timing, tiny queues, store-data "
        "dependencies, FU pipelining, branch recovery, precise faults and CLI behavior. "
        "Forty deterministic randomized programs run at each width, for 160 differential runs.")
    r.p("All tests pass. No known failing case remains in this tested scope. Timing "
        "checks complement the sequential interpreter, which checks final architectural "
        "state but does not model execution cycles.", SMALL)

    r.new_page("3 Results", "3.3  Reproduction and Sources", "sources")
    r.p("From the repository root, run the simulator and the checks with Python 3.9 or newer. "
        "The simulator needs no third-party packages.")
    r.code("cd Assignment1/Tomasulo\n"
           "python3 tomasulo-python/code/main.py\n"
           "python3 -m unittest discover -s tests -v\n"
           "python3 run_benchmarks.py", 9)
    r.p("To rebuild the reports, return to the repository root:", SMALL)
    r.code("python3 -m venv .report-venv\n"
           ".report-venv/bin/pip install -r requirements-report.txt\n"
           ".report-venv/bin/python scripts/build_assignment_reports.py", 8.6)
    r.p("The builder reruns all 36 cases and checks the saved traces and summary counts. "
        "Results must be regenerated before rebuilding a report if the simulator changes.", SMALL)
    r.heading("Sources and limitations")
    r.p("The supplied assignment handout defines the ISA, widths and timing rules. "
        "Sample_Tomasulo_Assignment_Report.pdf supplies the report format and the two sample "
        "test streams. The Python starter credits Qing, May 2017. Initial Version excerpts "
        "come from that starter; My Version excerpts come from the submitted source.", SMALL)
    r.p("Predictor updates at EX are not rolled back after a later squash. Memory replay "
        "can be conservative, and forwarding occupies the memory port for one cycle. "
        "Invalid accesses are reported at retirement. Retained instruction history grows "
        "with execution length. The arithmetic and hardware limitations are listed in Section 1.", SMALL)
    r.p("Codex assisted with implementation, testing and report preparation. "
        "All numerical tables were checked against the included code and saved outputs.", SMALL)
    r.p("Ali Alfageeh | October 15, 2026.<br/>"
        '<link href="https://github.com/fqeh/CompArchAssignment1/tree/main/Assignment1/Tomasulo">'
        'GitHub: fqeh/CompArchAssignment1 / Assignment1/Tomasulo</link>', SMALL)
    r.save()


if __name__ == "__main__":
    from build_assignment_reports import TOM, tomasulo_measurements
    build(TOM, *tomasulo_measurements())
