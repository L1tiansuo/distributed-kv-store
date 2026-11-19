#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 report/报告.md 转成排版好的 .docx。

只支持这份报告用到的语法：# 标题、正文、- 列表、1. 列表、| 表格 |、``` 代码块、
![图注](图片)、**加粗**、`行内代码`、--- 分页。
"""
import os
import re
import sys

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

BODY_CN = "宋体"
HEAD_CN = "黑体"
MONO = "Consolas"
INK = RGBColor(0x1C, 0x22, 0x33)
MUTED = RGBColor(0x60, 0x68, 0x80)


def cn_font(run, ascii_name="Times New Roman", cn_name=BODY_CN, size=None,
            bold=None, color=None, italic=None):
    run.font.name = ascii_name
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    rf.set(qn("w:eastAsia"), cn_name)
    rf.set(qn("w:ascii"), ascii_name)
    rf.set(qn("w:hAnsi"), ascii_name)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color


def shade(paragraph_or_cell, hexcolor):
    el = paragraph_or_cell._element
    pPr = el.get_or_add_pPr() if hasattr(el, "get_or_add_pPr") else el
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    pPr.append(shd)


def cell_shade(cell, hexcolor):
    tcPr = cell._element.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def add_page_number_footer(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run._element.addnext(fld)
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "1"
    r.append(t)
    fld.append(r)
    for run in p.runs:
        cn_font(run, size=9, color=MUTED)


INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def add_inline(paragraph, text, size=12, cn=BODY_CN, bold=False, color=INK):
    """处理 **加粗** 和 `行内代码`。"""
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            r = paragraph.add_run(part[2:-2])
            cn_font(r, cn_name=cn, size=size, bold=True, color=color)
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            r = paragraph.add_run(part[1:-1])
            cn_font(r, ascii_name=MONO, cn_name=MONO, size=size - 1.5,
                    color=RGBColor(0x3B, 0x4A, 0x6B))
        else:
            r = paragraph.add_run(part)
            cn_font(r, cn_name=cn, size=size, bold=bold, color=color)


def body_para(doc, text, indent=True, space_after=6, size=12):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = 1.5
    pf.space_after = Pt(space_after)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if indent:
        pf.first_line_indent = Pt(size * 2)
    add_inline(p, text, size=size)
    return p


def list_para(doc, text, marker="·"):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = 1.45
    pf.space_after = Pt(3)
    pf.left_indent = Pt(24)
    pf.first_line_indent = Pt(-12)
    r = p.add_run(marker + "  ")
    cn_font(r, size=12, color=MUTED)
    add_inline(p, text, size=12)
    return p


def heading(doc, text, level):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    if level == 1:
        pf.space_before = Pt(20)
        pf.space_after = Pt(10)
        size = 16
    elif level == 2:
        pf.space_before = Pt(14)
        pf.space_after = Pt(6)
        size = 13.5
    else:
        pf.space_before = Pt(10)
        pf.space_after = Pt(4)
        size = 12
    pf.keep_with_next = True
    # 用内置 Heading 样式保证导航窗格能用，再覆盖字体
    p.style = doc.styles["Heading %d" % min(level, 3)]
    pf2 = p.paragraph_format
    pf2.space_before = pf.space_before
    pf2.space_after = pf.space_after
    pf2.keep_with_next = True
    pf2.line_spacing = 1.3
    add_inline(p, text, size=size, cn=HEAD_CN, bold=True)
    return p


def code_block(doc, lines):
    for i, line in enumerate(lines):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.line_spacing = 1.15
        pf.space_after = Pt(0)
        pf.space_before = Pt(0)
        pf.left_indent = Pt(14)
        shade(p, "F5F6FA")
        r = p.add_run(line if line else " ")
        cn_font(r, ascii_name=MONO, cn_name=MONO, size=9, color=RGBColor(0x33, 0x3A, 0x50))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_table(doc, rows):
    header, body = rows[0], rows[1:]
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False

    # 列宽按内容长度分配，总宽 15.4cm
    total_cm = 15.4
    weights = []
    for c in range(len(header)):
        longest = max([len(header[c])] + [min(len(r[c]), 30) for r in body if c < len(r)])
        weights.append(max(longest, 4))
    wsum = sum(weights)
    widths = [Cm(total_cm * w / wsum) for w in weights]

    def style_cell(cell, text, bold=False, center=False):
        cell.text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(1.5)
        p.paragraph_format.space_after = Pt(1.5)
        p.paragraph_format.line_spacing = 1.1
        if center:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_inline(p, text, size=10.5, bold=bold)

    for i, h in enumerate(header):
        style_cell(t.rows[0].cells[i], h, bold=True, center=True)
        cell_shade(t.rows[0].cells[i], "EDF1FB")
    # 表头跨页重复、行内不允许断开
    trPr = t.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    th.set(qn("w:val"), "true")
    trPr.append(th)

    for row in body:
        cells = t.add_row().cells
        for i, val in enumerate(row[:len(header)]):
            style_cell(cells[i], val, center=(i > 0 and len(val) < 18))
        trPr2 = cells[0]._tc.getparent().get_or_add_trPr()
        cs = OxmlElement("w:cantSplit")
        cs.set(qn("w:val"), "true")
        trPr2.append(cs)

    for row in t.rows:
        for i, cell in enumerate(row.cells):
            cell.width = widths[i]

    # 让表格尽量整块落在同一页：除最后一行外，所有单元格段落都"与下段同页"
    for row in t.rows[:-1]:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.keep_with_next = True

    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(6)
    sp.paragraph_format.line_spacing = 1.0


def add_figure(doc, caption, path):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run()
    cands = [os.path.join(ROOT, "report", path), os.path.join(ROOT, "docs", path),
             os.path.join(ROOT, path)]
    full = next((c for c in cands if os.path.exists(c)), cands[0])
    run.add_picture(full, width=Cm(15.2))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(12)
    r = cap.add_run(caption)
    cn_font(r, size=9.5, color=MUTED)


def parse(md_text):
    blocks = []
    lines = md_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            blocks.append(("code", buf))
        elif line.startswith("!["):
            m = re.match(r"!\[(.+?)\]\((.+?)\)", line)
            if m:
                blocks.append(("fig", (m.group(1), m.group(2))))
        elif line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^[\s\-:|]+$", "".join(cells)):
                    rows.append(cells)
                i += 1
            blocks.append(("table", rows))
            continue
        elif line.startswith("### "):
            blocks.append(("h3", line[4:]))
        elif line.startswith("## "):
            blocks.append(("h2", line[3:]))
        elif line.startswith("# "):
            blocks.append(("h1", line[2:]))
        elif line.strip() == "---":
            blocks.append(("hr", None))
        elif re.match(r"^- ", line):
            blocks.append(("li", line[2:]))
        elif re.match(r"^\d+\. ", line):
            blocks.append(("li", line))
        elif line.strip() == "":
            blocks.append(("blank", None))
        else:
            blocks.append(("p", line))
        i += 1
    return blocks


def build(md_path, out_path):
    with open(md_path, encoding="utf-8") as f:
        text = f.read()
    blocks = parse(text)

    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21)
    sec.page_height = Cm(29.7)
    sec.left_margin = Cm(2.6)
    sec.right_margin = Cm(2.6)
    sec.top_margin = Cm(2.4)
    sec.bottom_margin = Cm(2.4)
    add_page_number_footer(sec)

    # 正文默认样式
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_CN)

    cover = True          # 第一个 --- 之前算封面
    for kind, payload in blocks:
        if kind == "h1":
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(96)
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(payload)
            cn_font(r, cn_name=HEAD_CN, size=23, bold=True)
        elif kind == "h2":
            if cover:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_after = Pt(54)
                r = p.add_run(payload)
                cn_font(r, cn_name=HEAD_CN, size=13.5, color=MUTED)
            else:
                heading(doc, payload, 1)
        elif kind == "h3":
            heading(doc, payload, 2)
        elif kind == "p":
            if cover:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.line_spacing = 1.5
                add_inline(p, payload, size=11)
            else:
                body_para(doc, payload)
        elif kind == "li":
            is_num = bool(re.match(r"^\d+\. ", payload))
            list_para(doc, payload, marker="" if is_num else "·")
        elif kind == "code":
            code_block(doc, payload)
        elif kind == "table":
            add_table(doc, payload)
        elif kind == "fig":
            add_figure(doc, payload[0], payload[1])
        elif kind == "hr":
            if cover:
                cover = False
                doc.add_page_break()
            else:
                sp = doc.add_paragraph()
                sp.paragraph_format.space_after = Pt(0)

    doc.save(out_path)
    print("已生成：", out_path)


if __name__ == "__main__":
    md = os.path.join(ROOT, "report", "报告.md")
    out = os.path.join(ROOT, "report", "分布式KV Store 课程报告.docx")
    build(md, out)
