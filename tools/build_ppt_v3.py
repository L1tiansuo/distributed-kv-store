#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成讲解用 PPT 第三版（v3）。

与 v2 的差异：
- 结构从 30 页扩到 48 页，新增「协议原理」与「实现与操作」两段
- 原理讲透：状态机、任期、投票约束、复制检查、冲突截断、提交规则、
  read-index、两层去重、原子性、持久化与恢复
- 融入真实代码片段与上机命令（均取自 src/ 与本机实跑输出）
- 新增三张图：日志复制、幂等余额、延迟分解
- 页面语言正式化：章节标题用名词，页标题用判断句；口语只留在备注讲稿里

输出：ppt/分布式KV Store 讲解_v3.pptx
"""
import os

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIG = os.path.join(ROOT, "docs", "figures")

# ---- 设计令牌 ----
INK = RGBColor(0x1C, 0x22, 0x33)
MUTED = RGBColor(0x68, 0x70, 0x8A)
NAVY = RGBColor(0x1F, 0x3A, 0x5F)
NAVY_L = RGBColor(0xE9, 0xEE, 0xF5)
ACCENT = RGBColor(0xD9, 0x77, 0x06)
CARD = RGBColor(0xF5, 0xF7, 0xFA)
LINE = RGBColor(0xD8, 0xDD, 0xEA)
GREEN = RGBColor(0x12, 0xA0, 0x5C)
RED = RGBColor(0xD9, 0x43, 0x3D)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

CODE_BG = RGBColor(0x16, 0x1C, 0x2A)
CODE_FG = RGBColor(0xE4, 0xE9, 0xF2)
CODE_CMT = RGBColor(0x82, 0x8F, 0xAB)
CODE_ACC = RGBColor(0xF0, 0xA8, 0x5C)

W, H = Inches(13.333), Inches(7.5)
FONT = "微软雅黑"
MONO = "Consolas"

prs = Presentation()
prs.slide_width = W
prs.slide_height = H
BLANK = prs.slide_layouts[6]

PAGE = [0]


def txbox(slide, x, y, w, h, text="", size=18, bold=False, color=INK,
          align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font=FONT, line=1.25):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = line
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    r.font.name = font
    return tb


def rect(slide, x, y, w, h, fill=CARD, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
         radius=0.06):
    sp = slide.shapes.add_shape(shape, x, y, w, h)
    sp.fill.solid()
    sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(1)
    sp.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sp.adjustments[0] = radius
        except Exception:
            pass
    return sp


def blank(fill=WHITE):
    s = prs.slides.add_slide(BLANK)
    rect(s, Inches(0), Inches(0), W, H, fill=fill, shape=MSO_SHAPE.RECTANGLE)
    return s


def slide_head(title, kicker=""):
    s = blank()
    if kicker:
        txbox(s, Inches(0.85), Inches(0.52), Inches(11), Inches(0.3), kicker,
              size=12, color=ACCENT, bold=True)
        txbox(s, Inches(0.85), Inches(0.82), Inches(11.7), Inches(0.6), title,
              size=26, bold=True, color=NAVY)
    else:
        txbox(s, Inches(0.85), Inches(0.62), Inches(11.7), Inches(0.7), title,
              size=27, bold=True, color=NAVY)
    rect(s, Inches(0.85), Inches(1.5), Inches(0.72), Inches(0.045), fill=ACCENT,
         shape=MSO_SHAPE.RECTANGLE)
    return s


def footer(s, note=""):
    PAGE[0] += 1
    txbox(s, Inches(0.85), Inches(6.95), Inches(9), Inches(0.3),
          "分布式 KV Store · 并行与分布", size=10, color=MUTED)
    txbox(s, Inches(12.0), Inches(6.95), Inches(0.6), Inches(0.3),
          "%02d" % PAGE[0], size=10, color=MUTED, align=PP_ALIGN.RIGHT)
    if note:
        s.notes_slide.notes_text_frame.text = note
    return s


def bullets(s, items, x=Inches(0.9), y=Inches(1.85), w=Inches(11.6),
            size=17, gap=10, h=Inches(4.6)):
    tb = s.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for it in items:
        text, level = (it if isinstance(it, tuple) else (it, 0))
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.line_spacing = 1.32
        p.space_after = Pt(gap if level == 0 else 4)
        p.level = level
        bullet = "▪  " if level == 0 else "–  "
        r = p.add_run()
        r.text = bullet + text
        r.font.size = Pt(size - (2 if level else 0))
        r.font.color.rgb = INK if level == 0 else MUTED
        r.font.name = FONT
    return tb


def metrics(s, items, top=Inches(2.05), height=Inches(2.78), size=32):
    n = len(items)
    gap = Inches(0.32)
    total_w = Inches(11.6)
    cw = Emu(int((total_w - gap * (n - 1)) / n))
    for i, (num, label, sub) in enumerate(items):
        x = Inches(0.85) + Emu(int(i * (cw + gap)))
        rect(s, x, top, cw, height, fill=WHITE, line=LINE)
        rect(s, x, top, cw, Inches(0.06), fill=ACCENT, shape=MSO_SHAPE.RECTANGLE)
        txbox(s, x + Inches(0.3), top + Inches(0.34), cw - Inches(0.5),
              Inches(0.8), num, size=size, bold=True, color=NAVY)
        txbox(s, x + Inches(0.3), top + Inches(1.16), cw - Inches(0.5),
              Inches(0.4), label, size=13, bold=True, color=INK)
        txbox(s, x + Inches(0.3), top + Inches(1.62), cw - Inches(0.5),
              height - Inches(1.75), sub, size=11, color=MUTED, line=1.3)


def add_table(s, headers, rows, col_w, top=Inches(1.9), size=12,
              header_size=12, row_h=Inches(0.4), left=None):
    total = sum(col_w)
    x = Inches(left) if left is not None else Emu(int((W - Inches(total)) / 2))
    shape = s.shapes.add_table(len(rows) + 1, len(headers), x, top,
                               Inches(total), Emu(int(row_h * (len(rows) + 1))))
    tbl = shape.table
    for i, wd in enumerate(col_w):
        tbl.columns[i].width = Inches(wd)
    for c, hh in enumerate(headers):
        cell = tbl.cell(0, c)
        cell.text = ""
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY_L
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_left = Inches(0.09)
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER
        r = p.add_run()
        r.text = hh
        r.font.size = Pt(header_size)
        r.font.bold = True
        r.font.color.rgb = NAVY
        r.font.name = FONT
    for ri, row in enumerate(rows, start=1):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.text = ""
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if ri % 2 else CARD
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Inches(0.09)
            cell.margin_right = Inches(0.05)
            cell.text_frame.word_wrap = True
            p = cell.text_frame.paragraphs[0]
            pure_num = not any("一" <= ch <= "鿿" for ch in str(val))
            p.alignment = (PP_ALIGN.CENTER if pure_num and len(str(val)) <= 8
                           else PP_ALIGN.LEFT)
            r = p.add_run()
            r.text = str(val)
            r.font.size = Pt(size)
            r.font.color.rgb = INK
            r.font.name = FONT
    return tbl


def two_col(s, left_title, left_items, right_title, right_items,
            left_color=NAVY, right_color=GREEN, top=Inches(1.85),
            height=Inches(4.0), size=13):
    cw = Inches(5.6)
    for i, (t, items, color) in enumerate(((left_title, left_items, left_color),
                                          (right_title, right_items, right_color))):
        x = Inches(0.85) + Emu(int(i * (cw + Inches(0.4))))
        rect(s, x, top, cw, height, fill=WHITE, line=LINE)
        txbox(s, x + Inches(0.35), top + Inches(0.26), cw - Inches(0.7),
              Inches(0.4), t, size=15, bold=True, color=color)
        tb = s.shapes.add_textbox(x + Inches(0.35), top + Inches(0.8),
                                  cw - Inches(0.7), height - Inches(1.0))
        tf = tb.text_frame
        tf.word_wrap = True
        first = True
        for it in items:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.line_spacing = 1.3
            p.space_after = Pt(7)
            r = p.add_run()
            r.text = "· " + it
            r.font.size = Pt(size)
            r.font.color.rgb = INK
            r.font.name = FONT


def code_box(s, lines, x=Inches(0.85), y=Inches(1.85), w=Inches(11.6),
             size=11, title=""):
    """深底代码块，注释手动着色。lines 为字符串列表，行首空格即缩进。"""
    line_h = size * 1.4 / 72.0
    pad = 0.24
    h = Inches(pad * 2 + line_h * len(lines))
    rect(s, x, y, w, h, fill=CODE_BG, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.03)
    if title:
        txbox(s, Emu(int(x + w - Inches(3.6))), Emu(int(y + Inches(0.05))),
              Inches(3.4), Inches(0.24), title, size=8.5, color=CODE_CMT,
              align=PP_ALIGN.RIGHT)
    tb = s.shapes.add_textbox(x + Inches(pad), y + Inches(pad - 0.03),
                              Emu(int(w - Inches(pad * 2))), Emu(int(h - Inches(pad))))
    tf = tb.text_frame
    tf.word_wrap = False
    tf.margin_left = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    first = True
    for ln in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.line_spacing = Pt(size * 1.4)
        p.space_after = Pt(0)
        cut = ln.find("#")
        if cut >= 0:
            head, tail = ln[:cut], ln[cut:]
        else:
            head, tail = ln, ""
        r = p.add_run()
        r.text = head if head else " "
        r.font.size = Pt(size)
        r.font.name = MONO
        r.font.color.rgb = CODE_FG
        if tail:
            r2 = p.add_run()
            r2.text = tail
            r2.font.size = Pt(size)
            r2.font.name = MONO
            r2.font.color.rgb = CODE_CMT
    return h


def term_box(s, lines, x=Inches(0.85), y=Inches(1.85), w=Inches(11.6),
             size=11, title="终端"):
    """命令与输出，命令以 > 开头，输出的行另色。"""
    line_h = size * 1.4 / 72.0
    pad = 0.24
    h = Inches(pad * 2 + line_h * len(lines))
    rect(s, x, y, w, h, fill=CODE_BG, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.03)
    txbox(s, Emu(int(x + w - Inches(3.6))), Emu(int(y + Inches(0.05))),
          Inches(3.4), Inches(0.24), title, size=8.5, color=CODE_CMT,
          align=PP_ALIGN.RIGHT)
    tb = s.shapes.add_textbox(x + Inches(pad), y + Inches(pad - 0.03),
                              Emu(int(w - Inches(pad * 2))), Emu(int(h - Inches(pad))))
    tf = tb.text_frame
    tf.word_wrap = False
    tf.margin_left = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    first = True
    for ln in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.line_spacing = Pt(size * 1.4)
        p.space_after = Pt(0)
        is_cmd = ln.startswith(">")
        r = p.add_run()
        r.text = ln if ln else " "
        r.font.size = Pt(size)
        r.font.name = MONO
        r.font.color.rgb = CODE_ACC if is_cmd else CODE_FG
    return h


def flow(s, items, y=Inches(2.7), x=Inches(0.85), w=Inches(11.6),
         h=Inches(1.15), gap=Inches(0.3), size=12, numbered=True):
    """横向流程，items 为字符串或 (标题, 说明)。"""
    n = len(items)
    cw = Emu(int((w - gap * (n - 1)) / n))
    for i, it in enumerate(items):
        title, sub = (it if isinstance(it, tuple) else (it, ""))
        bx = x + Emu(int(i * (cw + gap)))
        rect(s, bx, y, cw, h, fill=WHITE, line=LINE)
        if numbered:
            rect(s, bx + Inches(0.16), y + Inches(0.16), Inches(0.34),
                 Inches(0.34), fill=NAVY, shape=MSO_SHAPE.OVAL)
            txbox(s, bx + Inches(0.16), y + Inches(0.19), Inches(0.34),
                  Inches(0.28), str(i + 1), size=11, bold=True, color=WHITE,
                  align=PP_ALIGN.CENTER)
        txbox(s, bx + Inches(0.16), y + Inches(0.58), cw - Inches(0.3),
              Inches(0.34), title, size=size, bold=True, color=NAVY,
              align=PP_ALIGN.CENTER if not numbered else PP_ALIGN.LEFT)
        if sub:
            txbox(s, bx + Inches(0.16), y + Inches(0.92), cw - Inches(0.3),
                  Inches(0.5), sub, size=9.5, color=MUTED, line=1.2)
        if i < n - 1:
            ar = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW,
                                    Emu(int(bx + cw + Inches(0.04))),
                                    Emu(int(y + h / 2 - Inches(0.09))),
                                    Inches(0.22), Inches(0.18))
            ar.fill.solid()
            ar.fill.fore_color.rgb = ACCENT
            ar.line.fill.background()


def pic(s, name, x=None, y=Inches(1.8), max_w=Inches(11.2),
        max_h=Inches(4.7)):
    path = os.path.join(FIG, name)
    with Image.open(path) as im:
        iw, ih = im.size
    ratio = min(max_w / iw, max_h / ih)
    w, h = Emu(int(iw * ratio)), Emu(int(ih * ratio))
    left = x if x is not None else Emu(int((W - w) / 2))
    return s.shapes.add_picture(path, left, y, width=w, height=h)


def section(num, title, sub, note):
    s = blank()
    rect(s, Inches(0), Inches(0), Inches(0.22), H, fill=NAVY,
         shape=MSO_SHAPE.RECTANGLE)
    txbox(s, Inches(1.2), Inches(1.9), Inches(3.2), Inches(1.6),
          num, size=80, bold=True, color=NAVY_L)
    txbox(s, Inches(1.25), Inches(3.5), Inches(10.8), Inches(0.9),
          title, size=31, bold=True, color=NAVY)
    txbox(s, Inches(1.28), Inches(4.45), Inches(10.4), Inches(1.0),
          sub, size=15, color=MUTED, line=1.5)
    return footer(s, note)


# ============================ 01 问题定义 ============================
s = blank()
rect(s, Inches(0), Inches(0), Inches(0.28), H, fill=NAVY, shape=MSO_SHAPE.RECTANGLE)
txbox(s, Inches(1.3), Inches(1.55), Inches(11), Inches(0.36),
      "并行与分布 · 课程设计", size=14, color=ACCENT, bold=True)
txbox(s, Inches(1.3), Inches(2.05), Inches(11.2), Inches(1.5),
      "分布式 KV Store 的设计与实现", size=40, bold=True, color=NAVY)
txbox(s, Inches(1.32), Inches(3.35), Inches(10.6), Inches(0.9),
      "三副本强一致键值存储：协议原理、工程实现与实验评估", size=18, color=INK)
rect(s, Inches(1.32), Inches(4.28), Inches(1.1), Inches(0.05), fill=ACCENT,
     shape=MSO_SHAPE.RECTANGLE)
txbox(s, Inches(1.32), Inches(4.62), Inches(6), Inches(0.4),
      "组员：____________　____________　____________", size=13, color=MUTED)
txbox(s, Inches(1.32), Inches(5.06), Inches(9), Inches(0.4),
      "https://github.com/L1tiansuo/distributed-kv-store", size=12, color=MUTED)
footer(s, "开场不念标题。先说一句：这套系统只用 Python 标准库，三个独立进程，"
          "所有数字都在 results/ 里，随时可以翻。今天讲三件事——为什么这么设计、协议怎么工作、实验证明了什么。")

# 目录
s = slide_head("汇报结构", "目录")
items = [
    ("01", "问题定义", "业务场景、失效模型、设计目标与关键选择"),
    ("02", "协议原理", "选主、日志复制、提交、线性读、幂等与持久化"),
    ("03", "实现与操作", "代码结构、核心数据结构、上机流程"),
    ("04", "实验结果", "故障转移、脑裂、幂等、性能与代价"),
    ("05", "反思与结论", "实现缺陷、能力边界、结论"),
]
for i, (num, t, sub) in enumerate(items):
    y = Inches(1.85 + i * 0.92)
    txbox(s, Inches(0.9), y, Inches(0.8), Inches(0.5), num, size=20, bold=True,
          color=ACCENT)
    txbox(s, Inches(1.72), y - Inches(0.04), Inches(3.4), Inches(0.45), t,
          size=18, bold=True, color=NAVY)
    txbox(s, Inches(5.0), y, Inches(7.3), Inches(0.45), sub, size=13, color=MUTED)
    rect(s, Inches(0.9), Emu(int(y + Inches(0.62))), Inches(11.5),
         Emu(int(9144)), fill=LINE, shape=MSO_SHAPE.RECTANGLE)
footer(s, "五段式：问题、原理、实现、证据、反思。前两段占一半时间，"
          "因为老师追问多半落在原理上；第三段是现场操作时要用的，讲的时候可以快过。")

section("01", "问题定义", "业务场景、失效模型，以及为什么选单主复制",
        "第一部分只做一件事：说清楚我们在什么约束下做设计。八个候选场景里为什么选银行转账，"
        "以及这个场景逼出了哪些必须回答的问题。")

# 场景
s = slide_head("五个账户与一条不变式", "业务场景")
txbox(s, Inches(0.9), Inches(1.78), Inches(6.2), Inches(0.4),
      "账户初始状态（reset 之后）", size=12, color=MUTED)
add_table(s, ["账户", "余额", "版本号"],
          [["A", "1000", "1"], ["B", "1000", "1"], ["C", "1000", "1"],
           ["D", "1000", "1"], ["E", "1000", "1"]],
          [1.5, 1.6, 1.9], top=Inches(2.18), size=13, row_h=Inches(0.42), left=0.85)
rect(s, Inches(7.3), Inches(1.78), Inches(5.1), Inches(1.35), fill=NAVY_L)
txbox(s, Inches(7.62), Inches(1.95), Inches(4.5), Inches(0.3),
      "不变式", size=10.5, bold=True, color=ACCENT)
txbox(s, Inches(7.62), Inches(2.3), Inches(4.5), Inches(0.6),
      "A + B + C + D + E = 5000", size=17, bold=True, color=NAVY)
txbox(s, Inches(0.9), Inches(4.86), Inches(5.6), Inches(1.3),
      "系统全部业务只有三个操作：\n"
      "· transfer：从 src 扣款、向 dst 加款，金额可指定\n"
      "· cas：版本号匹配才写入，用于并发控制\n"
      "· get：按键读取余额与版本号",
      size=13, color=INK, line=1.6)
txbox(s, Inches(7.3), Inches(3.32), Inches(5.1), Inches(2.2),
      "为什么用这个不变式\n"
      "每次操作后重新求和，多一分或少一分即刻暴露。\n"
      "不需要额外工具，也不需要争论什么算「丢数据」。",
      size=13, color=MUTED, line=1.7)
footer(s, "五个账户、每个一千块，总额五千。这个数字是整场汇报的验收线："
          "后面杀主、分区、重复请求，每次操作完都回到这个五千上对账。")

# 为什么选这个场景
s = slide_head("选择依据：可验证性优先于功能丰富度", "选题")
two_col(s, "功能丰富的场景", [
    "订单、库存、会话等多种数据模型",
    "正确性依赖业务规则，难以一眼判定",
    "出问题时需要逐条比对业务日志",
    "多种数据模型对应多套一致性问题",
    "演示效果依赖事先造数据",
], "不变式清晰的场景", [
    "单一账户模型，五个键",
    "正确性等价于一个算术等式",
    "任何偏差都能在页面上直接看到",
    "还原故障只需杀进程或断网",
    "演示时当场求和即可验证",
], right_color=GREEN, top=Inches(1.85), height=Inches(3.35), size=13)
txbox(s, Inches(0.9), Inches(5.52), Inches(11.5), Inches(0.8),
      "选择它不是因为业务简单，而是正确性可以当场验证：八个候选场景里，"
      "只有它不需要外部工具就能自证一致。",
      size=13, color=INK, line=1.5)
footer(s, "这一页回答「为什么选这么小的场景」。理由不是省事，是它有一个任何一致性"
          "问题都逃不过的检查。老師如果问「是不是太简单」，就从这一页的右栏答。")

# 四类失效
s = slide_head("从单机到分布式：四类新增失效", "问题来源")
cards = [
    ("进程崩溃", "任何一台随时可能退出，\n内存中的状态全部丢失", "靠副本与持久化"),
    ("网络分区", "机器都在运行，但彼此\n收不到消息，形成两半", "靠多数派"),
    ("消息异常", "延迟、重复、乱序，\n网络不保证一次送达", "靠幂等与序号"),
    ("时钟不可信", "各机器时间不一致，\n可能倒退，不能定序", "靠逻辑任期"),
]
for i, (t, d, fix) in enumerate(cards):
    x = Inches(0.85 + i * 2.95)
    rect(s, x, Inches(1.88), Inches(2.72), Inches(3.9), fill=WHITE, line=LINE)
    rect(s, x, Inches(1.88), Inches(2.72), Inches(0.06), fill=ACCENT,
         shape=MSO_SHAPE.RECTANGLE)
    txbox(s, x + Inches(0.26), Inches(2.14), Inches(2.2), Inches(0.4), t,
          size=16, bold=True, color=NAVY)
    txbox(s, x + Inches(0.26), Inches(2.72), Inches(2.2), Inches(1.1), d,
          size=12, color=INK, line=1.6)
    txbox(s, x + Inches(0.26), Inches(4.92), Inches(2.2), Inches(0.7),
          "对策：" + fix, size=11, bold=True, color=GREEN)
txbox(s, Inches(0.9), Inches(6.02), Inches(11.5), Inches(0.6),
      "单机程序只需要处理「代码写错了」；分布式系统还要处理「机器和网络不按预期工作」。",
      size=13, color=MUTED)
footer(s, "四类失效里，最容易被忽略的是第四类——时钟。很多同学会用时间戳判断先后，"
          "但机器时间会倒退。我们的做法是完全不用物理时钟定序，后面第 22 页专门讲。")

# 设计目标
s = slide_head("设计目标与非目标", "范围")
two_col(s, "本系统承诺", [
    "线性一致：读写都表现为单机语义",
    "容忍一台节点宕机，服务自动恢复",
    "已提交的写不丢失，重启后可重放",
    "同一请求重复提交只生效一次",
    "三节点、五账户规模下可完整演示",
], "本系统不承诺", [
    "跨地域低延迟写（需要多主）",
    "每秒万级吞吐（单主串行是上限）",
    "在线扩缩容（成员变更未实现）",
    "日志压缩（快照未实现）",
    "多键事务（只支持单条日志内的原子性）",
], left_color=GREEN, right_color=RED, top=Inches(1.85), height=Inches(4.1),
    size=13)
txbox(s, Inches(0.9), Inches(6.14), Inches(11.5), Inches(0.5),
      "目标与不做的部分同样重要：每一条「不做」都能说出代价，而不是来不及。",
      size=13, color=MUTED)
footer(s, "左栏是我们保证的，右栏是明确不做的。先把边界摆出来，后面被问到「为什么不支持」"
          "时，答案已经在台面上：不是做不到，是这样做要付别的代价。")

# 关键选择
s = slide_head("关键选择：单主复制与多数派提交", "方案对比")
add_table(s, ["", "单主复制（本项目）", "多主复制", "无主 quorum"],
          [["写冲突", "不存在：只有主接收写", "需要冲突解决策略", "需要版本向量或 CRDT"],
           ["读新鲜度", "线性读可保证", "可能读到旧值", "读 quorum 可调"],
           ["故障切换", "选主，0.4~1 秒", "天然多写点", "客户端直接换节点"],
           ["实现复杂度", "低：一套日志", "高：冲突合并", "中：读写 quorum 组合"],
           ["适用场景", "银行、配置、元数据", "多地区协同编辑", "高可用缓存"]],
          [1.9, 3.5, 3.0, 3.2], top=Inches(1.95), size=12, row_h=Inches(0.52))
txbox(s, Inches(0.9), Inches(5.7), Inches(11.5), Inches(1.0),
      "选择理由：本场景不能接受写冲突——余额不能「两边各扣一次再合并」。"
      "单主把冲突变成不发生，代价是所有写排在一个队列里。这个代价在第四部分量化。",
      size=13, color=INK, line=1.6)
footer(s, "三种方案没有优劣，只有适配。银行场景的关键约束是「写冲突不可合并」，"
          "所以单主是唯一能直接满足的。代价是吞吐上限，第 43 页会用数据说明这个上限在哪。")

# 系统全貌
s = slide_head("系统全貌", "架构")
pic(s, "fig_arch.png", y=Inches(1.78), max_w=Inches(10.6), max_h=Inches(4.55))
txbox(s, Inches(0.9), Inches(6.34), Inches(11.5), Inches(0.45),
      "三个独立进程、TCP 长连接、各自的 WAL 目录；控制台通过 HTTP 与集群交互。",
      size=12, color=MUTED)
footer(s, "三台机器各跑一个进程，各写各的日志文件。客户端连任意一台，写请求会被转到主节点。"
          "下面第二部分拆开讲：主是怎么选出来的，日志是怎么复制的。")

# ============================ 02 协议原理 ============================
section("02", "协议原理", "选主、日志复制、提交规则、线性读与幂等",
        "第二部分是全场最重的。按一条写请求的生命周期讲：谁当主、日志怎么复制、什么时候算提交、"
        "读怎么保证不旧、重试怎么不重复扣款。每页一个机制，配代码。")

# Raft 三子问题
s = slide_head("共识算法的三个子问题", "协议总览")
subs = [
    ("选主", "谁有权接收写请求", "任期内获得多数派投票的节点成为主；\n任期单调递增，旧主自动失效"),
    ("复制", "写怎么到其他节点", "主把日志项发给从节点，附带前一条的\n下标与任期做一致性检查"),
    ("安全", "什么算已提交", "多数派落盘且属于当前任期才提交；\n提交后的日志不会被覆盖"),
]
for i, (t, q, d) in enumerate(subs):
    x = Inches(0.85 + i * 3.95)
    rect(s, x, Inches(1.9), Inches(3.7), Inches(3.6), fill=WHITE, line=LINE)
    txbox(s, x + Inches(0.32), Inches(2.16), Inches(3.0), Inches(0.4),
          "0%d" % (i + 1), size=12, bold=True, color=ACCENT)
    txbox(s, x + Inches(0.32), Inches(2.54), Inches(3.0), Inches(0.45), t,
          size=20, bold=True, color=NAVY)
    txbox(s, x + Inches(0.32), Inches(3.14), Inches(3.0), Inches(0.4), q,
          size=12, color=ACCENT)
    txbox(s, x + Inches(0.32), Inches(3.62), Inches(3.05), Inches(1.6), d,
          size=12, color=INK, line=1.65)
txbox(s, Inches(0.9), Inches(5.78), Inches(11.5), Inches(0.7),
      "三者互相约束：没有正确选主，复制会分叉；没有提交规则，选主也无法保证不丢已提交的写。",
      size=13, color=MUTED)
footer(s, "Raft 把共识拆成三个问题。讲的时候按这个顺序：先有主，才能定序；定了序，才谈得上提交。"
          "这三块任何一块讲不清，后面所有实验都成了黑箱。")

# 状态机
s = slide_head("节点状态机", "选主基础")
states = [
    ("follower", "被动接收心跳与日志", "选举超时 → 转为 candidate"),
    ("candidate", "任期加一，向所有节点拉票", "获得多数票 → leader；发现更高任期 → follower"),
    ("leader", "接收写请求，向从节点复制日志", "发现更高任期 → follower"),
]
for i, (t, d, tr) in enumerate(states):
    x = Inches(0.85 + i * 3.95)
    rect(s, x, Inches(1.88), Inches(3.7), Inches(2.5), fill=WHITE, line=LINE)
    rect(s, x, Inches(1.88), Inches(3.7), Inches(0.06), fill=NAVY,
         shape=MSO_SHAPE.RECTANGLE)
    txbox(s, x + Inches(0.3), Inches(2.14), Inches(3.1), Inches(0.4), t,
          size=18, bold=True, color=NAVY, font=MONO)
    txbox(s, x + Inches(0.3), Inches(2.7), Inches(3.1), Inches(0.7), d,
          size=12, color=INK, line=1.5)
    txbox(s, x + Inches(0.3), Inches(3.52), Inches(3.1), Inches(0.7), tr,
          size=11, color=MUTED, line=1.4)
add_table(s, ["迁移", "触发条件", "本系统的处理"],
          [["follower → candidate", "选举超时（随机 300~600 ms）", "任期加一，投自己一票"],
           ["candidate → leader", "收到多数派投票", "立即追加一条空操作"],
           ["任意 → follower", "发现更高任期", "更新任期、清空投票、中止本地等待"]],
          [3.4, 4.4, 4.0], top=Inches(4.62), size=12, row_h=Inches(0.46))
footer(s, "三个状态、四条迁移。注意 candidate 转 leader 后立刻追加一条空操作——"
          "这条空操作没有业务含义，作用是把旧任期的日志顶到可提交的位置，第 19 页会解释。")

# 任期
s = slide_head("任期：不依赖物理时钟的逻辑序号", "定序机制")
txbox(s, Inches(0.9), Inches(1.8), Inches(11.4), Inches(0.5),
      "每个节点维护一个单调递增的整数 term。任期只增不减，收到更大的任期就立刻服从。",
      size=13, color=INK)
seg = [("term 1", "节点 1 当选", 0.9), ("term 2", "节点 1 宕机，节点 3 当选", 4.15),
       ("term 3", "节点 3 失联，节点 1 重新当选", 7.4)]
for label, ev, x in seg:
    rect(s, Inches(x), Inches(2.6), Inches(2.9), Inches(0.7), fill=NAVY_L,
         line=LINE)
    txbox(s, Inches(x), Inches(2.78), Inches(2.9), Inches(0.4), label, size=15,
          bold=True, color=NAVY, align=PP_ALIGN.CENTER)
    txbox(s, Inches(x), Inches(3.42), Inches(2.9), Inches(0.7), ev, size=10.5,
          color=MUTED, align=PP_ALIGN.CENTER, line=1.4)
for x in (3.92, 7.17):
    txbox(s, Inches(x), Inches(2.72), Inches(0.3), Inches(0.3), "→", size=16,
          color=ACCENT, align=PP_ALIGN.CENTER)
bullets(s, [
    "任期的两条规则：投票时带上自己的任期；收到更大任期立即降级为 follower",
    "同一任期最多一个 leader：当选需要多数派，而两份多数派必然有交集",
    "时间只用于触发选举（超时），不用于判断日志先后——先后由（任期, 下标）决定",
    "时钟倒退 60 秒的注入实验里，系统行为完全不变（见第 22 页）",
], y=Inches(4.34), size=13, gap=8, h=Inches(2.2))
footer(s, "任期是这套协议的骨架。它解决的是「谁说了算」：不比较机器时间，只比较数字大小。"
          "所以第 4 页说的第四类失效——时钟不可信——在这里被彻底绕开了。")

# 选主流程
s = slide_head("选主：四步完成一次权力交接", "选主流程")
flow(s, [
    ("选举超时", "follower 在 300~600 ms\n内没收到心跳"),
    ("转为候选", "term + 1，投自己一票，\n并行向其他节点拉票"),
    ("多数派投票", "得票 ≥ 2（三节点）\n即当选"),
    ("广播心跳", "立即追加空操作，\n确立新任期"),
], y=Inches(1.95), h=Inches(1.55), size=12)
txbox(s, Inches(0.9), Inches(3.86), Inches(5.6), Inches(0.4),
      "超时时间为什么是随机的", size=13, bold=True, color=NAVY)
txbox(s, Inches(0.9), Inches(4.28), Inches(5.5), Inches(1.3),
      "如果三台同时超时，会同时拉票、各得一票，谁也过不了半数，"
      "然后同时重试，陷入循环。随机化让其中一台先超时，先拿到票。",
      size=12, color=INK, line=1.6)
txbox(s, Inches(6.9), Inches(3.86), Inches(5.4), Inches(0.4),
      "实测的选主耗时", size=13, bold=True, color=NAVY)
txbox(s, Inches(6.9), Inches(4.28), Inches(5.4), Inches(1.3),
      "五轮宕机测试：390 / 436 / 480 / 527 / 1075 ms，中位数 480 ms。"
      "第一轮偏慢的原因在第 38 页说明。",
      size=12, color=INK, line=1.6)
footer(s, "四步：超时、拉票、过半、广播。随机超时是必须的，否则三台同时竞选会无限循环。"
          "如果老师问「为什么第一轮 1075 毫秒」，翻到第 38 页，那里有解释。")

# 投票规则
s = slide_head("投票的两条约束", "选主规则")
code_box(s, [
    "def on_request_vote(self, msg):",
    "    term = msg[\"term\"]",
    "    if term < self.current_term:",
    "        return {\"vote_granted\": False}      # 任期更旧，直接拒绝",
    "    if term > self.current_term:",
    "        self.current_term = term            # 见到新任期就服从",
    "        self.voted_for = None",
    "",
    "    up_to_date = (msg[\"last_term\"] > last_term or",
    "                  (msg[\"last_term\"] == last_term and",
    "                   msg[\"last_index\"] >= last_index))",
    "    if self.voted_for in (None, msg[\"from\"]) and up_to_date:",
    "        self.voted_for = msg[\"from\"]",
    "        self._persist_meta()                # 投票必须落盘",
    "        return {\"vote_granted\": True}",
], y=Inches(1.82), size=9.5, title="src/node.py · on_request_vote")
txbox(s, Inches(0.9), Inches(5.34), Inches(11.5), Inches(1.4),
      "约束一：同一任期只能投一票，且投票记录必须落盘——否则重启后可能投给两个人，"
      "同一任期出现两个 leader。\n"
      "约束二：只投给日志不比自己旧的候选者——日志较旧的节点当选，会覆盖已提交的日志。",
      size=13, color=INK, line=1.7)
footer(s, "两条约束。第一条容易漏：投票写进 meta.json 并且 fsync，不是内存里记一下。"
          "第二条防止「落后节点当选后覆盖已提交数据」，这是 Raft 安全性的关键一半。")

# 日志结构
s = slide_head("日志：每条记录都带任期", "数据结构")
pic(s, "fig_log.png", y=Inches(1.7), max_w=Inches(10.6), max_h=Inches(3.5))
bullets(s, [
    "下标 index 从 1 连续递增，不允许空洞",
    "任期 term 记录产生时的 leader 任期，用于冲突判断",
    "一旦在多数派落盘并提交，日志项不再被改写",
], y=Inches(5.42), size=12, gap=5, h=Inches(1.3))
footer(s, "日志不是简单的命令队列，每条都带着任期。图里节点 3 少最后一条，"
          "所以它的 next_index 是 7——主节点下次就从这里开始补。")

# 复制与一致性检查
s = slide_head("复制：用前一条日志做一致性检查", "日志复制")
code_box(s, [
    "prev = msg[\"prev_index\"]",
    "if prev > len(self.log) - 1:",
    "    return {\"success\": False, \"conflict_index\": len(self.log)}",
    "if self.log[prev][\"term\"] != msg[\"prev_term\"]:",
    "    return {\"success\": False, \"conflict_index\": ci}   # 快速回退",
    "",
    "for e in entries:",
    "    i = e[\"index\"]",
    "    if i <= len(self.log) - 1 and self.log[i][\"term\"] != e[\"term\"]:",
    "        del self.log[i:]                 # 冲突：截断自己的尾部",
    "    self.log.append(e)",
    "    self._append_wal(e)                  # 追加并落盘",
], y=Inches(1.8), size=9.5, title="src/node.py · on_append_entries")
txbox(s, Inches(0.9), Inches(4.82), Inches(11.5), Inches(1.5),
      "主节点每次携带「前一条的下标与任期」。从节点核对这两个值：对得上才接受新日志，"
      "对不上就拒绝并返回冲突位置，主节点据此把 next_index 往回退一格重试。\n"
      "这样只需要一次往返就能定位分叉点，不需要逐条比对整段日志。",
      size=13, color=INK, line=1.7)
footer(s, "核心是 prev_index 和 prev_term 这两个字段。它们相当于「我这条日志的前驱是第几条、"
          "哪个任期的」。从节点只要核对前驱，就能判断两边日志在这一点之前是否完全一致。")

# 冲突截断
s = slide_head("冲突处理：截断而不是合并", "日志安全")
add_table(s, ["情形", "从节点动作", "原因"],
          [["下标超出本地长度", "拒绝，返回本地长度", "本地还没有这条，需要先补齐前面的"],
           ["前驱任期不一致", "拒绝，返回冲突任期起点", "两边日志在此分叉，不能接"],
           ["同下标不同任期", "删除该位置之后的全部日志", "旧主任期未提交的日志必须让位"],
           ["同下标同任期", "跳过，继续比对下一条", "已经复制过，重复消息直接忽略"]],
          [3.2, 4.3, 4.3], top=Inches(1.92), size=12, row_h=Inches(0.5))
txbox(s, Inches(0.9), Inches(4.5), Inches(11.5), Inches(1.7),
      "为什么敢直接删除：能被截断的日志一定没有提交。提交需要多数派确认，"
      "而新主当选也需要多数派投票；两份多数派必然有交集，"
      "交集里的节点不会投票给日志落后的候选者。\n"
      "这条推理链是 Raft 安全性的全部内容，也是第 35 页「孤主写入被丢弃」的理论依据。",
      size=13, color=INK, line=1.75)
footer(s, "为什么可以放心删？因为能被删的日志一定没提交。如果不确定这点，"
          "就会怀疑「删日志是不是在丢数据」。这里的推理是：提交要多数派，选举也要多数派，"
          "两个多数派一定有交集，交集节点不会给落后的候选者投票。")

# 提交规则
s = slide_head("提交：多数派落盘且属于当前任期", "提交规则")
code_box(s, [
    "def _advance_commit(self):",
    "    idxs = sorted([self.match_index.get(p, 0) for p in self.peer_ids]",
    "                  + [len(self.log) - 1], reverse=True)",
    "    cand = idxs[self.quorum_size() - 1]        # 第 2 大的下标",
    "    if cand > self.commit_index and \\",
    "       self.log[cand][\"term\"] == self.current_term:",
    "        self.commit_index = cand",
    "        self._apply_committed()                # 立刻应用并唤醒客户端",
], y=Inches(1.82), size=10.5, title="src/node.py · _advance_commit")
txbox(s, Inches(0.9), Inches(4.0), Inches(5.5), Inches(0.4),
      "为什么要限制「当前任期」", size=13, bold=True, color=NAVY)
txbox(s, Inches(0.9), Inches(4.44), Inches(5.4), Inches(1.5),
      "旧任期的日志即使被多数派复制，也不能直接按计数提交——"
      "它可能在某次切换中被覆盖。只有当前任期的日志，才由当前主负责到底。",
      size=12, color=INK, line=1.65)
txbox(s, Inches(6.85), Inches(4.0), Inches(5.4), Inches(0.4),
      "空操作的作用", size=13, bold=True, color=NAVY)
txbox(s, Inches(6.85), Inches(4.44), Inches(5.4), Inches(1.5),
      "新主上任立刻追加一条空操作。它属于新任期，一旦提交，"
      "前面所有旧日志就随之被间接提交，不必等下一笔业务写。",
      size=12, color=INK, line=1.65)
footer(s, "两个细节：第一，只有当前任期的日志能按计数提交，旧任期的要等新任期日志带过去；"
          "第二，新主上任写一条空操作，就是为了尽快把旧日志带进可提交范围。")

# 写路径
s = slide_head("一次写请求的完整路径", "写路径")
flow(s, [
    ("接收", "客户端连接主节点\n或由从节点转发"),
    ("追加", "写入本地日志，\n追加到 log.jsonl"),
    ("复制", "并行发给两个\n从节点"),
    ("落盘", "各自 fsync，\n返回 match_index"),
    ("提交", "多数派确认后\n推进 commit_index"),
    ("应答", "应用状态机，\n唤醒等待的客户端"),
], y=Inches(1.95), h=Inches(1.5), size=11.5)
txbox(s, Inches(0.9), Inches(3.82), Inches(11.5), Inches(0.9),
      "整条路径是串行的：同一时刻只有一个写在这条流水线上。这是单主复制的本质，"
      "也是第 43 页吞吐上限的来源。",
      size=13, color=INK, line=1.6)
metrics(s, [("3.6 ms", "fsync 落盘", "单笔延迟的主要构成"),
            ("0.5 ms", "网络与处理", "三次 RPC 加状态机应用"),
            ("4.1 ms", "单笔总计", "并发 1 时的实测中位数")],
        top=Inches(4.72), height=Inches(1.9), size=26)
footer(s, "六步。注意第四步「落盘」是各自 fsync，不是收到就算——"
          "这是「写成功代表两台机器硬盘里都有」这句话的实际含义。"
          "3.6 毫秒的 fsync 占了单笔延迟的绝大部分。")

# read-index
s = slide_head("线性一致读：read-index 协议", "读路径")
flow(s, [
    ("记录目标", "取当前 commit_index\n作为 target"),
    ("发起心跳", "向两个从节点\n发一轮心跳"),
    ("收集应答", "收到多数派应答，\n说明自己仍是主"),
    ("等待应用", "确认 last_applied\n≥ target"),
    ("返回", "读取状态机，\n返回余额与版本"),
], y=Inches(1.95), h=Inches(1.5), size=11.5)
txbox(s, Inches(0.9), Inches(3.82), Inches(5.6), Inches(0.4),
      "为什么不能直接读本地", size=13, bold=True, color=NAVY)
txbox(s, Inches(0.9), Inches(4.26), Inches(5.45), Inches(1.6),
      "旧主被分区隔离后，本地数据可能已经过期，但它自己不知道。"
      "一轮心跳拿到多数派应答，才能确认没有被新主取代。",
      size=12, color=INK, line=1.65)
txbox(s, Inches(6.9), Inches(3.82), Inches(5.4), Inches(0.4),
      "拿不到多数派时", size=13, bold=True, color=NAVY)
txbox(s, Inches(6.9), Inches(4.26), Inches(5.4), Inches(1.6),
      "等 3 秒后返回 timeout_read，拒绝作答。宁可说「现在答不了」，"
      "也不返回一个可能过期的值。这就是第 40 页的对照实验。",
      size=12, color=INK, line=1.65)
footer(s, "read-index 的名字来自「读之前先确认自己还是主」。不读日志、不写日志，"
          "但要一轮心跳。代价是一次往返，换来的是绝不返回过期值。")

# 物理时钟
s = slide_head("为什么不用物理时钟定序", "定序依据")
two_col(s, "用时间戳定序的问题", [
    "各机器时钟有偏移，NTP 同步也有毫秒级误差",
    "时钟可能倒退（虚拟机迁移、校时）",
    "无法判断「A 的 10:00:00.100」和「B 的 10:00:00.050」谁先",
    "一旦判错，日志顺序与因果顺序不一致",
], "本系统的做法", [
    "顺序由（任期, 下标）唯一确定",
    "时间只用于触发选举超时",
    "任期是整数，只增不减，可持久化",
    "时钟倒退注入后，写入仍然成功且日志连续",
], right_color=GREEN, top=Inches(1.85), height=Inches(3.6), size=13)
txbox(s, Inches(0.9), Inches(5.62), Inches(11.5), Inches(0.9),
      "实验对照：把 leader 的时钟倒退 60 秒，写入正常提交，日志下标连续递增，"
      "任期不变（结果见 results/exp5_faults.json）。",
      size=13, color=INK, line=1.6)
footer(s, "这一页可以直接对第 4 页的第四类失效。老师常问「不用时钟怎么定序」，"
          "答案是（任期, 下标）这个二元组，它单调、可持久化、不受机器时间影响。")

# 幂等的由来
s = slide_head("重试是客户端的本能", "幂等（一）")
flow(s, [
    ("发出请求", "客户端写入\nreq_id = 订单号"),
    ("服务端执行", "扣款成功，\n但响应在网络上丢失"),
    ("客户端超时", "不知道成败，\n只能重试"),
    ("重复执行？", "若不去重，\n会再扣一次"),
], y=Inches(1.95), h=Inches(1.5), size=12)
txbox(s, Inches(0.9), Inches(3.86), Inches(11.5), Inches(0.9),
      "分布式系统里「超时」不等于「失败」。客户端唯一安全的选择是重试，"
      "而重试就必须由服务端保证只生效一次。",
      size=13, color=INK, line=1.6)
txbox(s, Inches(0.9), Inches(4.78), Inches(11.4), Inches(0.4),
      "实验对照（exp4，三组）", size=12, bold=True, color=NAVY)
add_table(s, ["场景", "请求次数", "实际扣款", "日志增长"],
          [["同一 req_id 连发三次", "3", "1 次（100 元）", "1 条"],
           ["不带 req_id 连发三次", "3", "3 次（300 元）", "3 条"],
           ["响应丢失后重试", "2", "1 次（100 元）", "1 条"]],
          [4.6, 2.2, 3.0, 2.2], top=Inches(5.02), size=12, row_h=Inches(0.4))
footer(s, "先讲问题再讲方案。超时不等于失败，客户端只能重试；不去重就会重复扣款。"
          "下面这张表是 exp4 的三组对照，第三组是「响应丢失」——三组里最难处理的一种。")

# 两层去重
s = slide_head("两层去重：内存快路径与状态机慢路径", "幂等（二）")
code_box(s, [
    "if req_id and req_id in self.dedup:",
    "    return dict(self.dedup[req_id], duplicate=True)   # 状态机层",
    "",
    "# 执行真正的业务逻辑 ...",
    "",
    "if req_id:",
    "    self.dedup[req_id] = result",
    "    while len(self.dedup) > DEDUP_CAP:",
    "        self.dedup.popitem(last=False)                 # 先进先出",
], y=Inches(1.85), size=10.5, title="src/node.py · _exec_cmd")
txbox(s, Inches(0.9), Inches(4.3), Inches(5.5), Inches(0.4),
      "为什么放在状态机里", size=13, bold=True, color=NAVY)
txbox(s, Inches(0.9), Inches(4.74), Inches(5.4), Inches(1.4),
      "去重表随日志一起复制。主节点切换后，新主的去重表与旧主一致，"
      "重试仍然能命中——如果只放 leader 内存，换主就失效。",
      size=12, color=INK, line=1.65)
txbox(s, Inches(6.85), Inches(4.3), Inches(5.4), Inches(0.4),
      "为什么还要内存快路径", size=13, bold=True, color=NAVY)
txbox(s, Inches(6.85), Inches(4.74), Inches(5.4), Inches(1.4),
      "重复请求不必再进一次日志。命中快路径直接返回，日志不增长——"
      "这是第 33 页三条命令 index 全为 4 的原因。",
      size=12, color=INK, line=1.65)
footer(s, "两层：leader 内存里先挡一次，挡不住就进日志、在状态机里再挡一次。"
          "关键是慢路径那份跟着日志复制，所以换主后仍然有效。这是「幂等跨故障仍然成立」的原因。")

# 原子性
s = slide_head("原子性：一条日志项即一笔事务", "转账")
code_box(s, [
    "elif op == \"transfer\":",
    "    a, b = self.kv.get(src), self.kv.get(dst)",
    "    if a[\"value\"] < amount:",
    "        result = {\"ok\": False, \"error\": \"insufficient_funds\"}",
    "    else:",
    "        a[\"value\"] -= amount;  a[\"version\"] += 1",
    "        b[\"value\"] += amount;  b[\"version\"] += 1",
    "        # 两个账户在同一条日志项里修改：要么都成，要么都不成",
], y=Inches(1.85), size=10.5, title="src/node.py · _exec_cmd（transfer 分支）")
txbox(s, Inches(0.9), Inches(4.24), Inches(11.4), Inches(0.4),
      "与两阶段提交的对比", size=13, bold=True, color=NAVY)
add_table(s, ["", "两阶段提交（2PC）", "单日志项（本项目）"],
          [["协调者", "需要独立的协调者与事务表", "由 leader 兼任，无额外组件"],
           ["失败恢复", "需要查询全局事务状态", "日志重放即可，天然幂等"],
           ["适用边界", "跨多个分片、多个存储", "单个状态机内的多键修改"],
           ["本项目结论", "未采用", "五账户同属一个状态机，够用"]],
          [2.6, 4.6, 4.4], top=Inches(4.62), size=11.5, row_h=Inches(0.4))
footer(s, "转账的原子性不靠 2PC，靠「一条日志项里改两个账户」。日志项要么整体提交、"
          "要么整体不存在，中间态在日志层面就不存在。这是省掉代码最多的一处设计。")

# 持久化
s = slide_head("持久化：哪些必须 fsync", "存储")
add_table(s, ["文件", "内容", "写入方式", "理由"],
          [["log.jsonl", "日志项，追加写", "每笔 fsync", "已提交的写不能丢"],
           ["meta.json", "当前任期、投票对象", "变更即 fsync", "防止重启后重复投票"],
           ["commit_index", "提交位置", "定时 flush，不 fsync", "可由日志重放推导"]],
          [2.5, 3.6, 3.4, 3.3], top=Inches(1.9), size=12, row_h=Inches(0.46))
txbox(s, Inches(0.9), Inches(3.98), Inches(5.6), Inches(0.4),
      "为什么 commit_index 可以不落盘", size=13, bold=True, color=NAVY)
txbox(s, Inches(0.9), Inches(4.34), Inches(5.45), Inches(1.71),
      "它是日志的推导结果：重启后重放日志，能提交到哪一条是可以重新算出来的。"
      "落盘只是为了加快启动，丢了大不了多算一遍。",
      size=12, color=INK, line=1.65)
txbox(s, Inches(6.85), Inches(3.98), Inches(5.4), Inches(0.4),
      "代价与收益", size=13, bold=True, color=NAVY)
txbox(s, Inches(6.85), Inches(4.34), Inches(5.4), Inches(1.71),
      "每笔 fsync 约 3.6 ms。若把 commit_index 也 fsync，写路径上会多一次磁盘等待，"
      "p99 从 9 ms 涨到 63 ms（实测）。",
      size=12, color=INK, line=1.65)
footer(s, "三条判断标准：不能从别处算出来的，必须 fsync；能算出来的，不浪费这次等待。"
          "任期和投票属于前者，commit_index 属于后者。这个区分把 p99 从 63 毫秒降到 9 毫秒。")

# 崩溃恢复
s = slide_head("崩溃恢复：从磁盘重建状态", "恢复流程")
flow(s, [
    ("读 meta", "恢复任期\n与投票对象"),
    ("重放日志", "从 log.jsonl\n逐条执行"),
    ("重建状态机", "得到重启前的\n账本与版本号"),
    ("追平日志", "向主节点请求\n缺失部分"),
], y=Inches(1.95), h=Inches(1.5), size=12)
txbox(s, Inches(0.9), Inches(3.86), Inches(11.5), Inches(1.0),
      "重放是幂等的：每条日志项带 req_id，重复执行会命中去重表，不会重复扣款。"
      "所以「重放到一半再次崩溃」也不会算错账。",
      size=13, color=INK, line=1.6)
txbox(s, Inches(0.9), Inches(4.9), Inches(11.4), Inches(0.4),
      "实测数据", size=12, bold=True, color=NAVY)
add_table(s, ["场景", "恢复方式", "耗时", "结果"],
          [["进程被 kill 后重启", "重放 WAL + 追平", "527 ms", "账本一致，总额 5000"],
           ["落后节点恢复通信", "日志复制追平", "1072 ms", "三副本一致"]],
          [4.2, 3.6, 2.4, 3.0], top=Inches(5.28), size=11.5, row_h=Inches(0.44))
footer(s, "恢复分两步：本地重放，然后向主节点补差。重放本身幂等，所以中途再崩也没关系。"
          "表里三个场景都是实测，第三个是分区恢复后落后节点追平。")

# ============================ 03 实现与操作 ============================
section("03", "实现与操作", "代码结构、核心数据结构，以及一次完整的上机流程",
        "第三部分是现场操作要用的。左边讲代码怎么组织，右边给命令和输出。"
        "讲的时候可以快过，但这几页决定了被问到「你们怎么跑的」时能不能立刻演示。")

# 代码结构
s = slide_head("代码结构：四个文件，一个实验目录", "工程")
add_table(s, ["文件", "行数", "职责"],
          [["src/node.py", "约 780", "单节点完整实现：选主、复制、提交、read-index、状态机、持久化、故障注入"],
           ["src/client.py", "约 290", "客户端：连接复用、主节点重定向、重试、压测"],
           ["src/run.py", "约 430", "集群管理进程：拉起三个节点、HTTP API、控制台服务"],
           ["src/console.html", "约 300", "单页控制台：节点卡片、账本、操作区、事件时间线"],
           ["experiments/", "6 个脚本", "故障转移、脑裂、幂等、故障模型、性能，输出 results/*.json"],
           ["tools/", "4 个脚本", "报告 docx、图表、两版 PPT 的生成脚本"]],
          [2.9, 1.9, 6.8], top=Inches(1.92), size=11.5, row_h=Inches(0.5), left=0.85)
txbox(s, Inches(0.85), Inches(5.62), Inches(11.5), Inches(1.0),
      "总计约 1800 行，只用 Python 标准库：socket、json、threading、argparse。"
      "没有 gRPC、没有 Redis、没有第三方依赖——每多一个依赖，就多一个「为什么用它」的问题。",
      size=13, color=INK, line=1.6)
footer(s, "四个文件分工清楚。老师如果问「哪部分是你写的」，就按这四块说：协议、客户端、运维、界面。"
          "行数是实测的 wc -l，可以当场打开指给他看。")

# 核心数据结构
s = slide_head("核心数据结构：一个 Node 类装下全部状态", "工程")
code_box(s, [
    "# ---- Raft 持久状态（写 meta.json / log.jsonl）----",
    "self.current_term = 0",
    "self.voted_for = None",
    "self.log = [{\"term\": 0, \"index\": 0}]   # 下标 0 是哨兵",
    "self.commit_index = 0",
    "",
    "# ---- 易失状态（重启后重建）----",
    "self.state = \"follower\"",
    "self.next_index = {}     # 每个从节点下一条要发的位置",
    "self.match_index = {}    # 每个从节点已确认复制到的位置",
    "",
    "# ---- 状态机 ----",
    "self.kv = {}             # key -> {\"value\", \"version\"}",
    "self.dedup = OrderedDict()   # req_id -> 结果（随日志复制）",
    "self.waiters = {}        # 日志下标 -> 等待中的客户端",
], y=Inches(1.8), size=9.5, title="src/node.py · Node.__init__（节选）")
txbox(s, Inches(0.85), Inches(5.3), Inches(11.6), Inches(1.2),
      "持久状态必须落盘，易失状态可以重建，状态机是日志的函数。崩溃恢复因此只需重放日志。",
      size=13, color=INK, line=1.65)
footer(s, "代码里特意把三类状态注释分开：持久、易失、状态机。这不是摆样子——"
          "写持久化的时候，只要问「这个字段属于哪一类」，就知道该不该 fsync。")

# 启动集群
s = slide_head("启动：三个进程、三个端口、三个数据目录", "操作一")
term_box(s, [
    "> python src/run.py --fresh",
    "[10:37:37] 启动节点 1（进程 14444）",
    "[10:37:37] 启动节点 2（进程 2804）",
    "[10:37:37] 启动节点 3（进程 25080）",
    "[10:37:37] 集群已启动：3 个节点，端口 [7301, 7302, 7303]",
    "控制台: http://127.0.0.1:8080",
], y=Inches(1.9), size=11)
txbox(s, Inches(0.85), Inches(4.0), Inches(5.5), Inches(0.4),
      "参数说明", size=13, bold=True, color=NAVY)
txbox(s, Inches(0.85), Inches(4.44), Inches(5.4), Inches(1.6),
      "--fresh：启动前清空 data/，从同一初始状态开始\n"
      "--fsync：默认开启，演示落盘代价时可用 --no-fsync 对照\n"
      "启动后会自动清理上次残留的进程，避免端口占用",
      size=12, color=INK, line=1.7)
txbox(s, Inches(6.85), Inches(4.0), Inches(5.4), Inches(0.4),
      "启动后先确认", size=13, bold=True, color=NAVY)
txbox(s, Inches(6.85), Inches(4.44), Inches(5.4), Inches(1.6),
      "浏览器打开 8080，看三张节点卡片是否有一张标 LEADER；"
      "或执行 curl /api/cluster 看 leader 字段。选主通常在 1 秒内完成。",
      size=12, color=INK, line=1.7)
footer(s, "先起三个进程，再说清楚 --fresh 的作用。如果现场只剩一个节点活着，"
          "控制台会一直显示「选主中」——那不是 bug，是凑不出多数派。")

# 正常读写
s = slide_head("读写：一条命令看完整链路", "操作二")
term_box(s, [
    "> python src/client.py reset --amount 1000",
    "{\"ok\": true, \"index\": 2, \"result\": {\"accounts\": {\"A\": 1000, ...}}}",
    "> python src/client.py get A",
    "{\"ok\": true, \"result\": {\"value\": 1000, \"version\": 1}, \"index\": 2, \"node\": 1}",
    "> python src/client.py transfer A B 100",
    "第1次: {\"ok\": true, \"index\": 3, \"balance_from\": 900, \"balance_to\": 1100}",
], y=Inches(1.86), size=10)
txbox(s, Inches(0.85), Inches(4.42), Inches(5.5), Inches(0.4),
      "三个字段的含义", size=13, bold=True, color=NAVY)
txbox(s, Inches(0.85), Inches(4.86), Inches(5.4), Inches(1.6),
      "index：这条操作在复制日志中的位置\n"
      "leader：本次由哪个节点处理\n"
      "node：实际应答的节点（线性读必定是主）",
      size=12, color=INK, line=1.7)
txbox(s, Inches(6.85), Inches(4.42), Inches(5.4), Inches(0.4),
      "读为什么要带 node", size=13, bold=True, color=NAVY)
txbox(s, Inches(6.85), Inches(4.86), Inches(5.4), Inches(1.6),
      "如果读由从节点应答，就必须先向主确认，否则可能返回旧值。"
      "本系统统一由主应答，node 字段可以直接验证这一点。",
      size=12, color=INK, line=1.7)
footer(s, "reset 之后读一次，确认五个账户各 1000。注意读返回的 node 一定是主节点——"
          "这是线性读的可观察特征。如果 node 出现从节点，说明读路径写错了。")

# 幂等验证
s = slide_head("幂等验证：三次请求，一条日志", "操作三")
term_box(s, [
    "> python src/client.py transfer A B 100 --times 3",
    "第1次: {\"ok\": true, \"index\": 4, ..., \"balance_from\": 800, ...}",
    "第2次: {\"ok\": true, \"index\": 4, ..., \"duplicate\": true}",
    "第3次: {\"ok\": true, \"index\": 4, ..., \"duplicate\": true}",
], y=Inches(1.86), size=10.5)
txbox(s, Inches(0.85), Inches(3.62), Inches(11.5), Inches(0.9),
      "三次 index 完全相同，日志没有增长；后两次带 duplicate，返回的是第一次的结果。"
      "A 只从 900 变成 800，不是 600。",
      size=13, color=INK, line=1.6)
add_table(s, ["观察项", "连发三次", "如果不去重"],
          [["日志下标", "三次都是 4", "4 / 5 / 6"],
           ["A 的余额", "800（只扣一次）", "600（扣三次）"],
           ["返回标记", "后两次 duplicate", "无"]],
          [3.0, 5.0, 4.0], top=Inches(4.6), size=12, row_h=Inches(0.42))
txbox(s, Inches(0.85), Inches(6.42), Inches(11.5), Inches(0.3),
      "输出中的 ... 为省略的字段，完整 JSON 见报告附录 D。", size=10, color=MUTED)
footer(s, "这是最值得现场做的一步：三条命令，三次 index 全一样，钱只扣一次。"
          "口头解释不如让老师看 index 那一列。")

# 杀主
s = slide_head("故障演示：杀掉当前主节点", "操作四")
term_box(s, [
    "> curl -X POST http://127.0.0.1:8080/api/killleader",
    "{\"ok\": true, \"killed\": 1}",
    "",
    "# 约两秒后查询集群状态",
    "节点 1  已宕机",
    "节点 2  follower  term 2",
    "节点 3  leader    term 2",
], y=Inches(1.86), size=10.5)
txbox(s, Inches(0.85), Inches(4.5), Inches(5.5), Inches(0.4),
      "发生了什么", size=13, bold=True, color=NAVY)
txbox(s, Inches(0.85), Inches(4.94), Inches(5.4), Inches(1.3),
      "节点 2、3 收不到心跳，选举超时后由 3 号拉起投票，"
      "拿到两票当选，任期从 1 升到 2。",
      size=12, color=INK, line=1.7)
txbox(s, Inches(6.85), Inches(4.5), Inches(5.4), Inches(0.4),
      "客户端感受", size=13, bold=True, color=NAVY)
txbox(s, Inches(6.85), Inches(4.94), Inches(5.4), Inches(1.3),
      "切换期间写请求会失败一次，客户端带重试，自动导向新主。"
      "账本不变，总额仍为 5000。",
      size=12, color=INK, line=1.7)
footer(s, "杀主是最直观的一步。看两件事：任期加了 1，新主是自己选出来的，没有人干预。"
          "切换窗口大约半秒，期间客户端会失败一次。")

# 分区
s = slide_head("故障演示：网络分区与孤主拒写", "操作五")
term_box(s, [
    "> curl -X POST -d '{\"groups\":[[3],[1,2]]}' .../api/partition",
    "{\"ok\": true}",
    "",
    "> python src/client.py --ports 7303 set A 123      # 孤主",
    "{\"ok\": false, \"error\": \"timeout_unknown\", \"index\": 8, \"leader\": 3}",
    "",
    "> python src/client.py --ports 7301 transfer C D 50  # 多数派",
    "第1次: {\"ok\": true, \"index\": 7, \"leader\": 1}",
], y=Inches(1.86), size=10)
txbox(s, Inches(0.85), Inches(4.5), Inches(11.5), Inches(1.3),
      "分区后两半各有一个 leader：3 号停在任期 2，1 号在任期 3 拿到多数派。"
      "孤主的写返回 timeout_unknown 而不是 failed——它已经写进本地日志并落盘，"
      "但凑不齐多数派，无法确定将来是否会被提交。恢复网络后这条日志被截断丢弃。",
      size=12.5, color=INK, line=1.65)
txbox(s, Inches(0.85), Inches(5.96), Inches(11.5), Inches(0.5),
      "关键区别：少数派写不进去，多数派照常提交。这正是不把 quorum 从 2 改成 1 的理由。",
      size=12.5, bold=True, color=ACCENT)
footer(s, "这一步同时演示两件事：孤主拒写、多数派照常。而且返回的是 timeout_unknown，"
          "不是 failed——这个区别很重要，说明服务端自己也不知道结果。")

# ============================ 04 实验结果 ============================
section("04", "实验结果", "六组实验：故障转移、脑裂、幂等、故障模型、性能",
        "第四部分给数据。每组实验先说方法，再说数字，最后说这个数字意味着什么。"
        "所有结果都在 results/ 目录里，可以当场打开对照。")

# 实验方法
s = slide_head("实验方法：不加模拟层，三个进程直接跑", "测量原则")
items = [
    ("独立进程", "三个独立 Python 进程，\n各占一个端口，各自一个数据目录"),
    ("三轮取中位", "每个用例热身一次，\n跑三轮取中位数"),
    ("低干扰轮询", "只轮询存活进程，超时 0.12 s，\n避免测量本身拖慢系统"),
    ("结果落盘", "每个实验输出 json，\n报告中的数字可逐项复算"),
]
for i, (t, d) in enumerate(items):
    x = Inches(0.85 + (i % 2) * 5.95)
    y = Inches(1.9 + (i // 2) * 2.05)
    rect(s, x, y, Inches(5.65), Inches(1.8), fill=WHITE, line=LINE)
    txbox(s, x + Inches(0.32), y + Inches(0.24), Inches(5.0), Inches(0.4), t,
          size=15, bold=True, color=NAVY)
    txbox(s, x + Inches(0.32), y + Inches(0.76), Inches(5.0), Inches(0.9), d,
          size=12, color=INK, line=1.6)
txbox(s, Inches(0.85), Inches(6.02), Inches(11.5), Inches(0.6),
      "不用模拟器的原因：模拟器测不出 fsync 的代价，也测不出发送缓冲区对延迟的影响。",
      size=12.5, color=MUTED)
footer(s, "四条原则，核心是第一条：不模拟。第二条和第三条是踩过坑才加的——"
          "一开始只跑一次，数字忽高忽低；轮询所有节点时，测量本身也在抢 CPU。")

# 故障转移
s = slide_head("故障转移：五轮宕机，数据零丢失", "实验一")
pic(s, "fig_failover.png", x=Inches(0.85), y=Inches(1.7), max_w=Inches(6.2), max_h=Inches(2.85))
add_table(s, ["轮次", "故障节点", "新 leader", "选主耗时", "重启追平"],
          [["1", "1", "2", "1075 ms", "527 ms"],
           ["2", "2", "3", "527 ms", "512 ms"],
           ["3", "3", "1", "480 ms", "498 ms"],
           ["4", "1", "2", "390 ms", "470 ms"],
           ["5", "2", "3", "436 ms", "455 ms"]],
          [1.5, 2.0, 2.0, 2.5, 2.5], top=Inches(4.72), size=11, row_h=Inches(0.32))
txbox(s, Inches(7.35), Inches(1.86), Inches(5.2), Inches(2.7),
      "第一轮为什么慢\n\n"
      "· 落后节点先超时，先投了自己一票\n"
      "· 这一轮票被浪费，要再等一次超时\n"
      "· 这是 pre-vote 要解决的问题\n"
      "· 我们没有实现，但把代价记在数据里",
      size=12, color=MUTED, line=1.65)
footer(s, "五轮全部成功，数据零丢失。第一轮 1075 毫秒要主动解释：落后节点先超时白拉了一票。"
          "这不是实现错误，是没做 pre-vote 的已知代价。")

# 分区与脑裂
s = slide_head("分区与脑裂：quorum 的实际含义", "实验二")
pic(s, "fig_split.png", x=Inches(0.85), y=Inches(1.7), max_w=Inches(6.4), max_h=Inches(2.8))
add_table(s, ["场景", "结果", "说明"],
          [["失去多数派", "写入 timeout_unknown（3005 ms）", "leader 仍自称主，commit 不前进"],
           ["恢复一个从节点", "1072 ms 后恢复写入", "补票后立即提交"],
           ["quorum 改成 1", "两侧都能写", "同一笔钱可能被两边各扣一次"]],
          [3.0, 5.2, 4.0], top=Inches(4.6), size=11, row_h=Inches(0.42))
txbox(s, Inches(7.5), Inches(1.86), Inches(5.0), Inches(2.7),
      "quorum=1 的代价\n\n"
      "· 分区时两半都能写入\n"
      "· 系统看起来「更可用」\n"
      "· 但两边各记一套账，恢复后无法合并\n"
      "· 可用性提高的代价，是「写成功」失去含义",
      size=12, color=MUTED, line=1.65)
footer(s, "这一页回答「quorum 从 2 改成 1 会失去什么」。失去的不是性能，是「写成功」这三个字的分量："
          "分区时两边都能写，恢复后账对不上，而且没有任何办法合并。")

# 脏读对照
s = slide_head("读一致性：同一时刻的两个值", "实验三")
add_table(s, ["读取方式", "节点", "返回", "耗时"],
          [["脏读 --stale", "孤主（3 号）", "C = 1000，version 1，index 5", "即时"],
           ["线性读", "多数派（1 号）", "C = 950，version 2，index 7", "4 ms"],
           ["线性读", "孤主（3 号）", "timeout_read，拒绝作答", "6.8 s"]],
          [3.0, 2.9, 4.6, 2.2], top=Inches(2.0), size=12, row_h=Inches(0.5))
txbox(s, Inches(0.85), Inches(4.0), Inches(11.5), Inches(1.0),
      "分区期间多数派完成了一笔 C→D 50，孤主并不知道。同一个 key、同一时刻，"
      "脏读给出一个看起来完全正常的 1000，而集群里的值已经是 950。",
      size=13, color=INK, line=1.65)
txbox(s, Inches(0.85), Inches(5.06), Inches(11.5), Inches(1.2),
      "两种选择的差别不是「快与慢」，而是「可能错」与「宁可不答」。"
      "默认路径选了后者：返回 timeout_read，让客户端重试或降级。",
      size=13, bold=True, color=NAVY, line=1.6)
footer(s, "这组对照最能说明线性读的价值。脏读的 1000 没有任何异常迹象，只有和多数派比对才知道过期。"
          "如果没有对照组，就说不清默认路径到底保护了什么。")

# 幂等实验
s = slide_head("幂等：三次请求只扣一次", "实验四")
pic(s, "fig_idem.png", x=Inches(0.85), y=Inches(1.8), max_w=Inches(6.6),
    max_h=Inches(3.6))
txbox(s, Inches(7.9), Inches(1.86), Inches(4.6), Inches(0.4),
      "三组对照", size=13, bold=True, color=NAVY)
txbox(s, Inches(7.9), Inches(2.3), Inches(4.55), Inches(3.4),
      "① 同一 req_id 连发三次\n"
      "   日志只增 1 条，扣款 1 次\n\n"
      "② 不带 req_id 连发三次\n"
      "   日志增 3 条，扣款 3 次\n\n"
      "③ 响应丢失后重试\n"
      "   服务端已扣款，重试命中\n"
      "   去重表，返回 duplicate\n\n"
      "结论：去重不是优化，是正确性\n"
      "的一部分。没有 req_id，重试\n"
      "就是重复扣款。",
      size=11.5, color=INK, line=1.65)
footer(s, "三组对照：带 req_id、不带 req_id、响应丢失。第二组是反例，证明不是「碰巧只扣一次」。"
          "第三组最难处理——服务端已经扣了，客户端没收到响应。")

# 性能
s = slide_head("吞吐与延迟：fsync 的代价", "实验五")
pic(s, "fig_perf.png", y=Inches(1.72), max_w=Inches(9.0), max_h=Inches(3.2))
add_table(s, ["配置", "并发", "吞吐", "p50", "p99"],
          [["fsync 开", "1", "253.8 ops/s", "3.7 ms", "7.3 ms"],
           ["fsync 开", "4", "374.3 ops/s", "10.3 ms", "14.5 ms"],
           ["fsync 开（单 key 热点）", "4", "360.6 ops/s", "10.6 ms", "15.2 ms"],
           ["fsync 关（对照）", "4", "4072 ops/s", "0.9 ms", "2.1 ms"]],
          [4.4, 1.4, 2.8, 2.1, 2.1], top=Inches(5.0), size=11, row_h=Inches(0.34))
footer(s, "fsync 关掉快 6.5 倍，但我们默认开着。理由不是保守：关掉之后重启，"
          "内存里那部分没落盘的写就没了。钱的事不能用「可能」记账。")

# 延迟与天花板
s = slide_head("延迟去向与单主上限", "实验六")
pic(s, "fig_latency.png", x=Inches(0.85), y=Inches(1.76), max_w=Inches(11.5),
    max_h=Inches(3.0))
txbox(s, Inches(0.85), Inches(4.94), Inches(5.5), Inches(0.4),
      "并发为什么救不了吞吐", size=13, bold=True, color=NAVY)
txbox(s, Inches(0.85), Inches(5.38), Inches(5.4), Inches(1.3),
      "并发从 1 加到 4，吞吐只从 254 涨到 374（+48%），延迟从 4.1 涨到 10.3 ms。"
      "多出来的不是并行，是排队。",
      size=12, color=INK, line=1.65)
txbox(s, Inches(6.85), Inches(4.94), Inches(5.4), Inches(0.4),
      "热点键的证据", size=13, bold=True, color=NAVY)
txbox(s, Inches(6.85), Inches(5.38), Inches(5.4), Inches(1.3),
      "单 key 热点 360.6，50 key 混合 374.3，几乎相同——说明所有写本来就在同一条队列里，"
      "没有「打散热点」的手段。",
      size=12, color=INK, line=1.65)
footer(s, "两个结论：延迟的 88% 花在 fsync；吞吐上限由单主串行决定，加机器无效——"
          "新加的机器只能当从节点，不接写。要突破只有批量提交或分片，我们都没做。")

# ============================ 05 反思 ============================
section("05", "反思与结论", "四个缺陷、四条边界，以及这套系统的定位",
        "最后一部分讲结果之外的东西：踩过的坑，和主动放弃的功能。"
        "这部分不需要背，挑自己最有印象的讲，讲清楚比讲全重要。")

# 踩坑
s = slide_head("踩坑记录：四个缺陷", "实现")
add_table(s, ["现象", "根因", "修复"],
          [["换主后客户端收到「空操作成功」", "等待项按下标回填，新主 noop 占了同一位置",
            "等待项绑定日志对象，截断时立即作废"],
           ["单笔写延迟 100 ms", "只有心跳才触发复制，写要等下一个心跳",
            "有待复制日志就立即发送，不等心跳"],
           ["p99 突然涨到 63 ms", "定时持久化 meta 时调用了 fsync，卡住写路径",
            "定时保存只 flush，不 fsync"],
           ["新集群连到旧节点", "Windows 的 SO_REUSEADDR 允许抢占端口",
            "改用 SO_EXCLUSIVEADDRUSE，启动前清理残留"]],
          [3.5, 4.3, 4.4], top=Inches(1.95), size=11.5, row_h=Inches(0.62))
txbox(s, Inches(0.85), Inches(5.5), Inches(11.5), Inches(1.1),
      "第一个最典型：日志被截断后同一下标被空操作占据，客户端以为转账成功，其实钱没动。"
      "后三个分别落在写路径、持久化和启动流程上。",
      size=12.5, color=INK, line=1.6)
footer(s, "四个坑挑一个细讲，推荐第一个：客户端收到了空操作的结果，钱其实没转。"
          "修法是等结果时认准那条日志本身，不按位置认领。这种细节比「我们实现了 Raft」更有说服力。")

# 不足
s = slide_head("不足与边界", "边界")
two_col(s, "没有实现的", [
    "pre-vote：落后节点会白拉票，第一轮 1075 ms 就是代价",
    "日志快照：日志无限增长，长时间运行需要压缩",
    "成员变更：三节点写死，不支持在线扩缩容",
    "多主与跨地域：单主决定了写延迟的下限",
    "批量提交与分片：吞吐上限仍是 374 ops/s",
], "为什么不做", [
    "五轮实验中只影响一轮，收益小于复杂度",
    "五账户数据量小，演示周期内不会触发",
    "课程场景固定三节点，实现成本高",
    "银行场景不接受写冲突，多主不可选",
    "需要改提交路径与键空间划分，超出课程范围",
], left_color=RED, right_color=NAVY, top=Inches(1.85), height=Inches(4.1),
    size=12)
txbox(s, Inches(0.85), Inches(6.14), Inches(11.5), Inches(0.5),
      "每一条都答得出「为什么不做」，而不是「来不及」。边界清楚，比功能多更可信。",
      size=12.5, color=MUTED)
footer(s, "主动交代没做什么。重点是每一条都有理由，不是「来不及」。"
          "pre-vote 那条最好讲：第 38 页第一轮的 1075 毫秒就是它要解决的问题，我们没做，但把代价摆在数据里了。")

# 结论
s = slide_head("结论", "总结")
txbox(s, Inches(0.85), Inches(1.86), Inches(11.6), Inches(1.6),
      "三副本、单主复制、多数派落盘、两层幂等去重。\n"
      "这四件事换来不丢数据，代价是写延迟和吞吐上限。",
      size=22, bold=True, color=NAVY, line=1.6)
metrics(s, [("0", "数据丢失", "五轮杀主、一次脑裂演练"),
            ("390 ms", "最快选主", "最慢 1075 ms 也一并记录"),
            ("3 → 1", "重复请求", "同一 req_id 发三次只扣一次"),
            ("6.5×", "落盘的代价", "关 fsync 的吞吐差，我们选慢的")],
        top=Inches(3.28), height=Inches(2.3), size=26)
txbox(s, Inches(0.85), Inches(5.86), Inches(11.5), Inches(0.6),
      "五个账户，三台机器，总额从头到尾是 5000。", size=15, bold=True,
      color=ACCENT)
footer(s, "收尾停在这三句上。不要说「我们的系统还不完善」，直接说换到了什么、付出了什么："
          "不丢数据，代价是单笔 4.1 毫秒和 250 的吞吐上限。然后请老师提问。")

# 索引
s = slide_head("问题索引与仓库", "附录")
add_table(s, ["可能的提问", "回答所在页"],
          [["版本比较代码删掉会怎样", "第 18、25 页：冲突截断与 CAS"],
           ["写成功代表几个节点已保存", "第 19、20 页：多数派提交与写路径"],
           ["哪段执行能让客户端读到旧值", "第 21、40 页：read-index 与脏读对照"],
           ["quorum 从 2 改成 1 失去什么", "第 39 页：脑裂实验"],
           ["为什么不能只用物理时钟", "第 13、22 页：任期与时钟实验"],
           ["失败请求的 happens-before", "第 23、35 页：重试与孤主拒写"]],
          [6.4, 5.2], top=Inches(1.95), size=12, row_h=Inches(0.46))
txbox(s, Inches(0.85), Inches(5.46), Inches(11.5), Inches(0.4),
      "代码与数据", size=12, bold=True, color=NAVY)
txbox(s, Inches(0.85), Inches(5.86), Inches(11.5), Inches(0.7),
      "https://github.com/L1tiansuo/distributed-kv-store　"
      "（src/ 源码、results/ 原始数据、report/ 报告、ppt/ 讲稿）",
      size=12, color=MUTED, line=1.4)
footer(s, "这页是给自己看的提词器，不念。老师问到哪个问题，直接翻到对应页，指着数据回答。"
          "六个问题就是作业要求里那一页的原文。")

prs.save(os.path.join(ROOT, "ppt", "分布式KV Store 讲解_v3.pptx"))
print("已生成：ppt/分布式KV Store 讲解_v3.pptx，共 %d 页" % PAGE[0])
