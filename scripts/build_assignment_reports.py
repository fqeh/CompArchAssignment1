"""Build both Assignment 1 reports from checked source and saved measurements.

Run from any directory with Python 3.9+ and requirements-report.txt installed.
Supports the GitHub Assignment1/{BP,Tomasulo} layout and the local course folders.
"""
import csv
import hashlib
import re
import sys
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "Assignment1" / "BP"
TOM = ROOT / "Assignment1" / "Tomasulo"
if not BP.is_dir():
    BP = ROOT / "branch-prediction"
if not TOM.is_dir():
    TOM = ROOT / "o3-simulator"

PAGE_W, PAGE_H = A4
LEFT, BOTTOM = 56, 67
WIDTH = PAGE_W - 2 * LEFT
BODY = ParagraphStyle("Body", fontName="Times-Roman", fontSize=11,
                      leading=15, alignment=TA_LEFT, spaceAfter=9)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=9.3, leading=12, spaceAfter=7)
CELL = ParagraphStyle("Cell", parent=SMALL, fontSize=8.8, leading=11, spaceAfter=0)
CAPTION = ParagraphStyle("Caption", parent=SMALL, fontName="Times-Italic")


class Report:
    """Fixed, checked page layouts; long content fails instead of being clipped."""
    def __init__(self, path, short_title, title):
        self.path, self.short_title = path, short_title
        self.pdf = canvas.Canvas(str(path), pagesize=A4, invariant=1, pageCompression=1)
        self.pdf.setTitle(title)
        self.pdf.setAuthor("Ali Alfageeh")
        self.pdf.setSubject("Computer Architecture, Assignment 1")
        self.page, self.y = 0, 0

    def new_page(self, title):
        if self.page:
            self.pdf.showPage()
        self.page += 1
        c = self.pdf
        c.setFillColor(colors.black)
        c.setFont("Times-Roman", 9)
        c.drawString(LEFT, PAGE_H - 36, "Computer Architecture | Assignment 1")
        c.drawRightString(LEFT + WIDTH, PAGE_H - 36, self.short_title)
        c.setLineWidth(0.6)
        c.line(LEFT, PAGE_H - 43, LEFT + WIDTH, PAGE_H - 43)
        c.line(LEFT, 47, LEFT + WIDTH, 47)
        c.setFont("Times-Roman", 9)
        c.drawString(LEFT, 33, "Ali Alfageeh | October 15, 2026")
        c.drawRightString(LEFT + WIDTH, 33, str(self.page))
        self.y = PAGE_H - 76
        key = f"page-{self.page}"
        c.bookmarkPage(key)
        c.addOutlineEntry(title, key, level=0)
        self.heading(title, 17)

    def reserve(self, height):
        if self.y - height < BOTTOM:
            raise ValueError(f"{self.path.name}, page {self.page}: overflow by "
                             f"{BOTTOM - self.y + height:.1f} pt")

    def heading(self, text, size=12):
        if stringWidth(text, "Times-Bold", size) > WIDTH:
            raise ValueError(f"Heading too wide: {text}")
        spacing = 4 if size <= 12 else 0
        self.reserve(size + 13 + spacing)
        self.y -= spacing
        self.pdf.setFont("Times-Bold", size)
        self.pdf.drawString(LEFT, self.y, text)
        self.y -= size + 13

    def p(self, text, style=BODY):
        paragraph = Paragraph(text, style)
        _, height = paragraph.wrap(WIDTH, 1200)
        self.reserve(height + style.spaceAfter)
        paragraph.drawOn(self.pdf, LEFT, self.y - height + 3)
        self.y -= height + style.spaceAfter

    def code(self, text, size=8.5):
        lines = text.strip("\n").splitlines()
        for line in lines:
            if stringWidth(line, "Courier", size) > WIDTH - 20:
                raise ValueError(f"Code line too wide: {line}")
        leading = size * 1.35
        height = len(lines) * leading + 15
        self.reserve(height + 10)
        c = self.pdf
        c.setFillColor(colors.HexColor("#f3f3f3"))
        c.rect(LEFT, self.y - height, WIDTH, height, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Courier", size)
        for i, line in enumerate(lines):
            c.drawString(LEFT + 9, self.y - 12 - i * leading, line)
        self.y -= height + 10

    def table(self, rows, widths, compact=False):
        assert abs(sum(widths) - WIDTH) < 0.1
        content = []
        for row_index, row in enumerate(rows):
            content.append([Paragraph(("<b>" if row_index == 0 else "") + escape(str(value)) +
                                      ("</b>" if row_index == 0 else ""), CELL) for value in row])
        table = Table(content, colWidths=widths, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
            ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.black),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.black),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 2 if compact else 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2 if compact else 5),
        ]))
        _, height = table.wrap(WIDTH, 1400)
        self.reserve(height + 12)
        table.drawOn(self.pdf, LEFT, self.y - height)
        self.y -= height + 12

    def save(self):
        self.pdf.save()
        print(f"Created {self.path}: {self.page} pages, {self.path.stat().st_size:,} bytes")


def bp_measurements():
    with (BP / "results/benchmark.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    samples, total = rows[:-1], rows[-1]
    assert len(samples) == 20 and total["benchmark"] == "ALL"
    for name in ("instructions", "conditional_branches", "global_hits",
                 "always_taken_misses", "bimodal_misses", "gshare_misses", "hybrid_misses"):
        assert sum(int(row[name]) for row in samples) == int(total[name]), name
    for row in rows:
        for predictor in ("always_taken", "bimodal", "gshare", "hybrid"):
            calculated = int(row[predictor + "_misses"]) * 1000 / int(row["instructions"])
            assert abs(calculated - float(row[predictor + "_mpki"])) < 0.000001
    metadata = (BP / "results/environment.txt").read_text()
    checksums = re.findall(r"^([0-9a-f]{64})  (.+)$", metadata, re.M)
    assert len(checksums) == 5
    for expected, name in checksums:
        assert hashlib.sha256((BP / name).read_bytes()).hexdigest() == expected, name
    return samples, total


def branch_report():
    samples, total = bp_measurements()
    r = Report(BP / "Branch_Prediction_Report.pdf", "Branch prediction",
               "Assignment 1: Branch Predictor Implementation")
    r.new_page("1. Branch predictor implementation")
    r.p("<b>Ali Alfageeh</b><br/>October 15, 2026")
    r.p("This part of the assignment implements the branch-direction predictor in "
        "<font name='Courier'>pm_predictor</font>. It combines a bimodal table with a tagged global "
        "predictor. The global prediction is used when its tag matches; otherwise, the bimodal "
        "table supplies the answer. Both tables learn from the actual branch outcome.")
    r.p("The implementation uses the two-way global table allowed by the handout. Loop prediction, "
        "branch-target prediction and the Pentium M path information register are left out, as "
        "permitted. The result is the required subset of the predictor rather than a model of the "
        "complete Pentium M branch unit.")
    r.heading("Main result")
    r.p("Across the 20 supplied traces, the hybrid predictor averages <b>7.260 mispredictions per "
        "1,000 instructions (MPKI)</b>. The bimodal predictor averages 10.299 MPKI. The hybrid "
        "therefore improves on bimodal overall, although the supplied, larger gshare predictor "
        "performs better at 6.306 MPKI.")
    r.table([["Predictor", "Direction errors", "Average MPKI"],
             *[[label, f"{int(total[key + '_misses']):,}", f"{float(total[key + '_mpki']):.3f}"]
               for label, key in [("Always taken", "always_taken"), ("Bimodal", "bimodal"),
                                  ("Supplied gshare", "gshare"), ("Implemented hybrid", "hybrid")]]],
            [WIDTH - 225, 125, 100])
    r.heading("Files changed and added")
    r.p("The predictor is in <font name='Courier'>cbp2-infrastructure-v2/src/my_predictor.h</font>. "
        "The original driver and trace decoder are retained. The decoder's command pointer was "
        "made const so that it can hold string literals; the decoding algorithm was not changed.")
    r.p("The added predictor tests check state updates and replacement. A separate evaluator "
        "runs four predictors on the same trace, and <font name='Courier'>scripts/benchmark.py</font> "
        "collects their results and checks the hybrid against the original driver. This keeps the "
        "comparison and the required submission driver tied to the same implementation.")

    r.new_page("2. Predictor organization")
    r.table([["State", "Configuration"],
             ["Bimodal table", "4,096 two-bit counters; address bits [11:0] select a counter"],
             ["Global table", "512 sets, two ways per set; valid bit, six-bit tag and two-bit counter"],
             ["History", "15 most recent conditional outcomes; initially zero"],
             ["Replacement", "One LRU victim bit per set"],
             ["Initial state", "Bimodal counters are 1 (weakly not taken); global entries are invalid"]],
            [115, WIDTH - 115])
    r.p("The address/history lookup uses the following expressions. The XOR is a simple "
        "gshare-style choice for the hash that the assignment allows us to simplify.")
    r.code("bimodal_index = address & 0xFFF\n"
           "hash          = (address ^ history) & 0x7FFF\n"
           "global_set    = hash >> 6\n"
           "global_tag    = hash & 0x3F")
    r.p("A valid matching global tag overrides the bimodal prediction. A counter of 0 or 1 "
        "predicts not taken; 2 or 3 predicts taken. The lookup saves the selected indices, tag "
        "and hit way before any history update, so training changes the entry that made the prediction.")
    r.p("After a conditional branch resolves, its bimodal counter is trained. A global hit trains "
        "the matching counter. A miss allocates an invalid way if one exists, or replaces the LRU "
        "way otherwise. The new counter is 2 after taken and 1 after not taken. The accessed way "
        "becomes most recently used, then the actual outcome is shifted into the 15-bit history.")
    r.heading("A small check on the indexing")
    r.p("For address 0x44 and history 0, the bimodal index is 68, the global set is 1 and the "
        "tag is 4. Both global ways are initially invalid, so the cold prediction is not taken. "
        "If the branch is taken, the bimodal counter becomes 2, a global entry with counter 2 "
        "is allocated, and history becomes 1. The next lookup uses that new history.")
    r.p("Unconditional branches predict taken and do not train these direction tables. "
        "The logical storage is 8,192 bimodal bits + 9,216 global-entry bits + 512 replacement "
        "bits + 15 history bits = <b>17,935 bits</b>, or about 2.19 KiB. C++ storage is larger "
        "because counters and fields occupy bytes and the simulator keeps an update record.")

    r.new_page("3. Tests and measurement method")
    r.p("Seven deterministic test groups exercise the parts most likely to fail even when a "
        "predictor produces a plausible overall MPKI. The optimized test target passes all seven.")
    r.table([["Test group", "What it checks"],
             ["Cold state", "Invalid entries, zero tags, fallback, and lookup without training"],
             ["Indexing", "Hand-calculated hashes, large addresses and byte-address differences"],
             ["Counters and selection", "All two-bit transitions, saturation, both ways and global priority"],
             ["Replacement", "Invalid-way preference, LRU refresh, eviction and new-tag initialization"],
             ["Saved lookup", "Training uses the old index before history shifts"],
             ["Unconditional branches", "Direction state is unchanged for jumps, calls and returns"],
             ["Learning patterns", "Repeated taken, repeated not-taken and alternating outcomes"]],
            [120, WIDTH - 120])
    r.heading("Trace experiment")
    r.p("Each of the 20 course traces represents 100 million instructions. The full experiment "
        "therefore covers 2 billion instructions and 275,461,634 conditional branches. Each trace "
        "starts with fresh predictor state, including cold training; there is no discarded warm-up.")
    r.p("The evaluator compares always-taken, a 4,096-entry bimodal table, the supplied "
        "32,768-entry gshare and the hybrid on the same decoded outcomes. The hybrid and bimodal "
        "counters start weakly not taken. The supplied gshare retains its original strongly "
        "not-taken initialization.")
    r.code("MPKI = conditional direction errors * 1000 / instructions")
    r.p("This denominator counts instructions, not branches. The aggregate MPKI is also the "
        "arithmetic mean of the 20 trace values because all traces have equal instruction counts. "
        "The global hit rate is weighted by the number of conditional branches.")
    r.p("The saved experiment used macOS/arm64 and Apple Clang 17.0.0 with the supplied "
        "-g -O3 -Wall flags. The benchmark script checked each hybrid MPKI against the original "
        "driver. For this report, the saved counts and arithmetic were checked again, along with "
        "all five recorded source checksums and all 20 local trace checksums. The full trace "
        "experiment was not rerun just to format the PDF.", SMALL)

    r.new_page("4. Results on all 20 traces")
    r.p("All error columns are MPKI; lower is better. The last column is the fraction of "
        "conditional predictions that found a matching global entry.", SMALL)
    rows = [["Trace", "Always taken", "Bimodal", "Gshare", "Hybrid", "Global hit"]]
    for row in [*samples, total]:
        rows.append(["Average / total" if row["benchmark"] == "ALL" else row["benchmark"],
                     *[f"{float(row[name + '_mpki']):.3f}" for name in
                       ("always_taken", "bimodal", "gshare", "hybrid")],
                     f"{float(row['global_hit_rate_percent']):.2f}%"])
    r.table(rows, [WIDTH - 345, 75, 65, 65, 65, 75])
    r.p("Source: results/benchmark.csv. Values are rounded only for display. The CSV retains "
        "miss counts, instruction counts, hit counts and trace checksums.", CAPTION)
    r.p("The hybrid supplies 203,900,607 predictions from the global table, a hit rate of "
        "74.02%. A hit only means a matching tag was found; it does not mean the prediction "
        "was correct. The bimodal table supplies the remaining predictions.")

    r.new_page("5. Discussion and limitations")
    reduction = 100 * (1 - int(total["hybrid_misses"]) / int(total["bimodal_misses"]))
    r.p(f"The hybrid reduces total direction errors by <b>{reduction:.2f}% compared with bimodal</b> "
        "and improves on it in 19 of the 20 traces. History is particularly useful on 202.jess, "
        "where MPKI falls from 8.809 to 1.750. On 181.mcf it falls from 33.245 to 17.680. "
        "These results show the value of recording the context of a branch instead of relying "
        "only on its address.")
    r.p("The exception is 300.twolf. Its hybrid MPKI is 22.046, slightly worse than bimodal "
        "at 21.942. Only 32.68% of its conditional lookups hit in the global table, and a global "
        "hit always overrides the bimodal answer. The comparison shows a regression, but it "
        "does not isolate whether aliasing, replacement or that selection rule caused it.")
    r.heading("Comparison with the supplied gshare")
    r.p("Gshare averages 6.306 MPKI, compared with 7.260 for the hybrid. The hybrid beats "
        "gshare only on 256.bzip2, where the values are 0.076 and 0.094. It would be misleading "
        "to use this experiment to conclude that the hybrid organization is always worse: "
        "the supplied gshare has 32,768 counters, while the hybrid global table has only 1,024.")
    r.p("The supplied gshare uses 65,551 logical bits including its history, about 8 KiB. "
        "The hybrid uses about 2.19 KiB. The predictors also start with different counter states. "
        "A comparison at equal storage and equal initialization would be needed to separate "
        "the effect of organization from capacity and cold-start behavior.")
    r.heading("What works and what is outside this submission")
    r.p("The required bimodal/global lookup, two-bit training, tag checks, two-way replacement "
        "and conditional history updates are implemented. The deterministic tests pass, and "
        "the saved trace measurements agree with the assignment driver. There is no known "
        "failing case in the tests described here; those tests do not prove correctness for "
        "every possible trace.")
    r.p("The optional full Pentium M extra-credit class remains a starter skeleton. It is "
        "not used for the reported results. Target prediction, the loop predictor and PIR "
        "are omitted under the handout's allowed scope. The report also makes no claims "
        "about processor IPC, power or the timing cost of the predictor.")
    r.p("The main outcome is a working compact hybrid predictor with lower error rates than "
        "bimodal on most of these traces. Its weaker results against gshare and the small "
        "regression on twolf remain part of the result, rather than being excluded from the average.")

    r.new_page("6. Reproducing the results and sources")
    r.p("From the repository root, enter the BP folder and build the required driver and tests. "
        "A C++ compiler, make, Python 3.8+ and the decoder's gzip/bzip2 tools are needed.")
    r.code("cd Assignment1/BP\nmake -C cbp2-infrastructure-v2/src all test")
    r.p("Copy the course trace directory into cbp2-infrastructure-v2/traces, then run:")
    r.code("python3 scripts/benchmark.py\n"
           "cd cbp2-infrastructure-v2\n"
           "./src/predict traces/164.gzip/gzip.trace.bz2")
    r.p("The single-trace command prints 12.617 MPKI. The comparison script regenerates "
        "benchmark.csv, benchmark-summary.md, driver-results.txt and environment.txt in results/. "
        "The original csh runner is also supported. It truncates the mean to 7.259; rounding "
        "the exact aggregate gives 7.260.")
    r.heading("Rebuild both PDF reports")
    r.p("Run the following from the repository root. ReportLab is only needed for PDF creation.")
    r.code("python3 -m venv .report-venv\n"
           ".report-venv/bin/pip install -r requirements-report.txt\n"
           ".report-venv/bin/python scripts/build_assignment_reports.py")
    r.heading("Sources and attribution")
    r.p("1. <i>Assignment 1: Branch Predictor Implementation</i>, supplied course handout, "
        "especially pp. 1-3 and Appendix B. The required subset and two-way option come from this handout.", SMALL)
    r.p("2. Daniel A. Jimenez, supplied branch-prediction competition infrastructure. "
        "The trace reader, driver, gshare example, original runner and documentation were supplied "
        "with the course. See cbp2-infrastructure-v2/doc/index.html.", SMALL)
    r.p("3. Vladimir Uzelac and Aleksandar Milenkovic, <i>Experiment Flows and Microbenchmarks "
        "for Reverse Engineering of Branch Predictor Structures</i>, ISPASS 2009, pp. 207-217, "
        "DOI: 10.1109/ISPASS.2009.4919652. This is the background reference identified in the handout; "
        "the implementation decisions reported here are checked against the submitted source.", SMALL)
    r.p("No external cache implementation was used. Codex assisted with code, tests and report "
        "preparation. Numerical tables are based on the recorded program outputs.", SMALL)
    r.p('<link href="https://github.com/fqeh/CompArchAssignment1/tree/main/Assignment1/BP">'
        'Repository: fqeh/CompArchAssignment1 / Assignment1/BP</link>', SMALL)
    r.save()


def tomasulo_measurements():
    sys.path.insert(0, str(TOM / "tomasulo-python/code"))
    sys.path.insert(0, str(TOM / "tests"))
    from init import read_program
    from simulator import Simulator
    from reference import execute
    from print_status import format_result
    programs, runs = {}, {}
    for path in sorted((TOM / "benchmarks").glob("*.txt")):
        program = read_program(path)
        programs[path.stem] = program
        expected = execute(program)
        for width in range(1, 5):
            cpu = Simulator(program, width).run()
            assert (cpu.registers, cpu.memory, [e.pc for e in cpu.committed]) == expected
            saved = TOM / "results" / f"{path.stem}_w{width}.txt"
            assert saved.read_text() == format_result(cpu), f"Stale saved output: {saved}"
            runs[path.stem, width] = cpu
    with (TOM / "results/summary.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len(runs) == 36
    for row in rows:
        cpu = runs[row["benchmark"], int(row["issue_width"])]
        assert cpu.cycle == int(row["cycles"])
        assert len(cpu.committed) == int(row["committed"])
        assert cpu.mispredictions == int(row["mispredictions"])
        assert cpu.memory_replays == int(row["memory_replays"])
    return programs, runs


def tomasulo_report():
    from build_tomasulo_report import build
    build(TOM, *tomasulo_measurements())


if __name__ == "__main__":
    branch_report()
    tomasulo_report()
