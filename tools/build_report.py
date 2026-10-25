"""Build Ali Alfageeh's assignment report and exact source-code snapshots.

Optional report-building dependencies: reportlab, Pillow. The simulator itself
uses only the Python standard library. Run from any working directory.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import csv
import difflib
import hashlib
import json
import os
import re
import textwrap

from PIL import Image as PILImage, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                               TableStyle, Image, PageBreak, Preformatted)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'report_assets'
ASSETS.mkdir(exist_ok=True)
FONT_DIR = Path(os.environ.get('FONT_DIR', '/usr/share/fonts/truetype/dejavu'))
pdfmetrics.registerFont(TTFont('Body', str(FONT_DIR/'DejaVuSerif.ttf')))
pdfmetrics.registerFont(TTFont('BodyBold', str(FONT_DIR/'DejaVuSerif-Bold.ttf')))
pdfmetrics.registerFont(TTFont('Mono', str(FONT_DIR/'DejaVuSansMono.ttf')))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='BodyBold', italic='Body', boldItalic='BodyBold')
WIDTH, HEIGHT = A4
MARGIN = 52
CONTENT = WIDTH - MARGIN*2
STYLES = {
    'body': ParagraphStyle('body', fontName='Body', fontSize=9.2, leading=14, spaceAfter=8),
    'small': ParagraphStyle('small', fontName='Body', fontSize=8, leading=11.5, spaceAfter=6),
    'h1': ParagraphStyle('h1', fontName='BodyBold', fontSize=16, leading=21, spaceAfter=14),
    'h2': ParagraphStyle('h2', fontName='BodyBold', fontSize=11, leading=16, spaceAfter=8),
    'title': ParagraphStyle('title', fontName='BodyBold', fontSize=23, leading=30, spaceAfter=12),
    'caption': ParagraphStyle('caption', fontName='Body', fontSize=7.6, leading=10.5, alignment=TA_CENTER, spaceAfter=12),
    'code': ParagraphStyle('code', fontName='Mono', fontSize=8.1, leading=11),
}
STORY=[]
SNAPSHOTS=[]

def p(text, style='body'):
    STORY.append(Paragraph(text, STYLES[style]))

def heading(text):
    p(text, 'h1')

def newpage():
    STORY.append(PageBreak())

def table(rows, widths=None, size=8.3, padding=5):
    cellstyle=ParagraphStyle('cell',fontName='Body',fontSize=size,leading=size+3)
    data=[[Paragraph(escape(str(x)),cellstyle) for x in row] for row in rows]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9edf1')),
        ('LINEBELOW',(0,0),(-1,0),0.7,colors.black),
        ('LINEBELOW',(0,-1),(-1,-1),0.45,colors.black),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
        ('TOPPADDING',(0,0),(-1,-1),padding),('BOTTOMPADDING',(0,0),(-1,-1),padding),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f8f9fa')]),
    ]))
    STORY.append(t)
    STORY.append(Spacer(1,9))

def code_block(text, size=8):
    s=ParagraphStyle('codeblock',fontName='Mono',fontSize=size,leading=size*1.4,
                     leftIndent=8,spaceAfter=10)
    STORY.append(Preformatted(text,s))

def snippet(path, anchor, count):
    lines=(ROOT/path).read_text().splitlines()
    start=next(i for i,line in enumerate(lines) if anchor in line)
    return start+1,lines[start:start+count]

def snapshot(name,path,anchor,count,label):
    first,lines=snippet(path,anchor,count)
    # These are source snapshots: exact source text with original line numbers.
    # Long lines wrap only for presentation; they are not changed in source.
    drawlines=[]
    for index,line in enumerate(lines,first):
        wrapped=textwrap.wrap(line.expandtabs(4),width=99,replace_whitespace=False,
                              drop_whitespace=False) or ['']
        drawlines.extend([(str(index) if j==0 else '',chunk) for j,chunk in enumerate(wrapped)])
    scale=2
    mono=ImageFont.truetype(str(FONT_DIR/'DejaVuSansMono.ttf'),24)
    titlefont=ImageFont.truetype(str(FONT_DIR/'DejaVuSans.ttf'),23)
    w=1600; h=70+35*len(drawlines)+22
    im=PILImage.new('RGB',(w,h),'#f7f8fa')
    d=ImageDraw.Draw(im)
    d.rectangle((0,0,w-1,h-1),outline='#b4bdc5',width=2)
    d.rectangle((1,1,w-2,54),fill='#e7ebef')
    d.text((22,14),f'{label} | {path} | lines {first}-{first+len(lines)-1}',font=titlefont,fill='#253342')
    d.line((84,60,84,h-14),fill='#d8dce1',width=2)
    for row,(number,line) in enumerate(drawlines):
        y=67+35*row
        d.text((12,y),number,font=mono,fill='#6b7683')
        fill='#455f39' if line.lstrip().startswith('#') else '#182531'
        d.text((104,y),line,font=mono,fill=fill)
    dest=ASSETS/f'{name}.png'
    im.save(dest)
    SNAPS={'image':str(dest.relative_to(ROOT)), 'source':path,
           'start_line':first,'end_line':first+len(lines)-1,
           'source_sha256':hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),
           'text':'\n'.join(lines)}
    SNAPSHOTS.append(SNAPS)
    output_height=CONTENT*h/w
    STORY.append(Image(str(dest),width=CONTENT,height=output_height))
    STORY.append(Spacer(1,8))

def change(number,title,description,before,after,detail):
    newpage()
    heading(f'2.{number}  {title}')
    p(description)
    p('Initial version', 'h2')
    snapshot(f'change_{number}_before',*before,'BEFORE')
    p('My version', 'h2')
    snapshot(f'change_{number}_after',*after,'AFTER')
    p(f'Figure {number}. Before-and-after source snapshots. '+detail,'caption')

def interval(x):
    if not x: return '-'
    if isinstance(x,list): return str(x[0]) if len(x)==1 or x[0]==x[-1] else f'{x[0]}-{x[-1]}'
    return str(x)

def timing(result,width):
    p(f'Issue width {width} - {result["cycles"]} cycles', 'h2')
    rows=[['Instruction','ISSUE','EX','MEM','WB','COMMIT']]
    for ins in result['instructions']:
        if ins['status']!='committed':continue
        rows.append([ins['text'],interval(ins['issue']),interval(ins['ex']),
                     interval(ins['mem']),interval(ins['wb']),interval(ins['commit'])])
    widths=[CONTENT-240,44,53,53,40,50]
    # Compact tables deliberately fit two 17-instruction examples on one page.
    data=[[Paragraph(escape(str(x)),ParagraphStyle('tcell',fontName='Mono' if j==0 else 'Body',
           fontSize=6.9,leading=9.2)) for j,x in enumerate(row)] for row in rows]
    t=Table(data,colWidths=widths,repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9edf1')),
        ('LINEBELOW',(0,0),(-1,0),.5,colors.black),('LINEBELOW',(0,-1),(-1,-1),.4,colors.black),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f8f9fa')]),
        ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),3),
        ('TOPPADDING',(0,0),(-1,-1),2.2),('BOTTOMPADDING',(0,0),(-1,-1),2.2),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    STORY.append(t);STORY.append(Spacer(1,14))

def footer(canvas,doc):
    canvas.saveState()
    canvas.setFont('Body',8)
    canvas.drawString(MARGIN,HEIGHT-33,'Computer Architecture')
    canvas.drawRightString(WIDTH-MARGIN,HEIGHT-33,'Programming Assignment: Tomasulo')
    canvas.setLineWidth(.6);canvas.line(MARGIN,HEIGHT-39,WIDTH-MARGIN,HEIGHT-39)
    canvas.line(MARGIN,39,WIDTH-MARGIN,39)
    canvas.drawString(MARGIN,25,'Ali Alfageeh')
    canvas.drawRightString(WIDTH-MARGIN,25,f'Page {doc.page}')
    canvas.restoreState()

def save_report():
    (ASSETS/'snapshot_manifest.json').write_text(json.dumps(SNAPSHOTS,indent=2)+'\n')
    dest=ROOT/'Tomasulo_Assignment_Report_Ali_Alfageeh.pdf'
    doc=SimpleDocTemplate(str(dest),pagesize=A4,rightMargin=MARGIN,leftMargin=MARGIN,
                         topMargin=61,bottomMargin=54,title='Tomasulo Algorithm Implementation',
                         author='Ali Alfageeh',subject='Multi-issue simulation, source changes and measured validation')
    doc.build(STORY,onFirstPage=footer,onLaterPages=footer)
    print(dest)


if __name__=='__main__':
    # The authored sections are kept in a separate source for readability.
    exec((Path(__file__).with_name('report_sections.py')).read_text())
    save_report()
