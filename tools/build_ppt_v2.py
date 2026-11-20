#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成讲解用 PPT 第二版（v2）。

与 v1 的区别：
- 白底藏青学术配色（v1 是科技蓝）
- 面向小白听众：术语有首发权（Raft 到第 11 页才出现）、
  每个机制先给日常类比、每个数字都解释含义
- 纯讲解，无现场演示环节
- 30 页，每页备注是提词器级的逐字稿

输出：ppt/分布式KV Store 讲解_v2.pptx
"""
import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIG = os.path.join(ROOT, "docs", "figures")

# ---- 设计令牌（白底藏青学术版） ----
INK = RGBColor(0x1C, 0x22, 0x33)      # 正文主色
MUTED = RGBColor(0x68, 0x70, 0x8A)    # 次要文字
NAVY = RGBColor(0x1F, 0x3A, 0x5F)     # 标题装饰、主色
NAVY_L = RGBColor(0xE9, 0xEE, 0xF5)   # 藏青浅底
ACCENT = RGBColor(0xD9, 0x77, 0x06)   # 数据强调橙
CARD = RGBColor(0xF5, 0xF7, 0xFA)     # 卡片浅底
LINE = RGBColor(0xD8, 0xDD, 0xEA)     # 描边
GREEN = RGBColor(0x12, 0xA0, 0x5C)
RED = RGBColor(0xD9, 0x43, 0x3D)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

W, H = Inches(13.333), Inches(7.5)
FONT = "微软雅黑"

prs = Presentation()
prs.slide_width = W
prs.slide_height = H
BLANK = prs.slide_layouts[6]


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


def slide_head(title, kicker=""):
    s = prs.slides.add_slide(BLANK)
    rect(s, Inches(0), Inches(0), W, H, fill=WHITE, shape=MSO_SHAPE.RECTANGLE)
    if kicker:
        txbox(s, Inches(0.85), Inches(0.52), Inches(11), Inches(0.3), kicker,
              size=12, color=ACCENT, bold=True)
        txbox(s, Inches(0.85), Inches(0.82), Inches(11.6), Inches(0.6), title,
              size=27, bold=True, color=NAVY)
    else:
        txbox(s, Inches(0.85), Inches(0.62), Inches(11.6), Inches(0.7), title,
              size=28, bold=True, color=NAVY)
    rect(s, Inches(0.85), Inches(1.5), Inches(0.72), Inches(0.045), fill=ACCENT,
         shape=MSO_SHAPE.RECTANGLE)
    return s


def footer(s, idx, note):
    txbox(s, Inches(0.85), Inches(6.95), Inches(9), Inches(0.3),
          "分布式 KV Store · 并行与分布", size=10, color=MUTED)
    txbox(s, Inches(12.0), Inches(6.95), Inches(0.6), Inches(0.3), "%02d" % idx,
          size=10, color=MUTED, align=PP_ALIGN.RIGHT)
    if note:
        s.notes_slide.notes_text_frame.text = note


def bullets(s, items, x=Inches(0.9), y=Inches(1.85), w=Inches(11.6),
            size=17, gap=10):
    tb = s.shapes.add_textbox(x, y, w, Inches(4.6))
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
        r.font.bold = False
    return tb


def takeaway(s, text, top=Inches(6.15)):
    # 收束条已整体移除（2026-11-20 组内决定：页底不再放结论横条）。
    # 函数保留为空操作，免得逐页删调用点；各页的结论文案留在备注讲稿里讲。
    pass


def metrics(s, items, top=Inches(2.05)):
    n = len(items)
    gap = Inches(0.32)
    total_w = Inches(11.6)
    cw = Emu(int((total_w - gap * (n - 1)) / n))
    for i, (num, label, sub) in enumerate(items):
        x = Inches(0.85) + Emu(int(i * (cw + gap)))
        rect(s, x, top, cw, Inches(2.78), fill=WHITE, line=LINE)
        rect(s, x, top, cw, Inches(0.06), fill=ACCENT, shape=MSO_SHAPE.RECTANGLE)
        txbox(s, x + Inches(0.3), top + Inches(0.38), cw - Inches(0.5),
              Inches(0.8), num, size=34, bold=True, color=NAVY)
        txbox(s, x + Inches(0.3), top + Inches(1.22), cw - Inches(0.5),
              Inches(0.42), label, size=14, bold=True, color=INK)
        txbox(s, x + Inches(0.3), top + Inches(1.68), cw - Inches(0.5),
              Inches(0.95), sub, size=11, color=MUTED, line=1.25)


def add_table(s, headers, rows, col_w, top=Inches(1.9), size=13,
              header_size=13):
    total = sum(col_w)
    left = Emu(int((W - Inches(total)) / 2))
    shape = s.shapes.add_table(len(rows) + 1, len(headers), left, top,
                               Inches(total), Inches(0.36 * (len(rows) + 1)))
    tbl = shape.table
    for i, wd in enumerate(col_w):
        tbl.columns[i].width = Inches(wd)
    for c, h in enumerate(headers):
        cell = tbl.cell(0, c)
        cell.text = ""
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY_L
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = h
        r.font.size = Pt(header_size); r.font.bold = True
        r.font.color.rgb = NAVY; r.font.name = FONT
    for ri, row in enumerate(rows, start=1):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.text = ""
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if ri % 2 else CARD
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.06)
            cell.text_frame.word_wrap = True
            p = cell.text_frame.paragraphs[0]
            pure_num = not any('一' <= ch <= '鿿' for ch in str(val))
            p.alignment = (PP_ALIGN.CENTER if pure_num and len(str(val)) <= 8
                           else PP_ALIGN.LEFT)
            r = p.add_run(); r.text = str(val)
            r.font.size = Pt(size); r.font.color.rgb = INK; r.font.name = FONT
    return tbl


def two_col(s, left_title, left_items, right_title, right_items,
            left_color=NAVY, right_color=GREEN, top=Inches(1.9)):
    cw = Inches(5.6)
    for i, (t, items, color) in enumerate(((left_title, left_items, left_color),
                                          (right_title, right_items, right_color))):
        x = Inches(0.85) + Emu(int(i * (cw + Inches(0.4))))
        rect(s, x, top, cw, Inches(4.15), fill=WHITE, line=LINE)
        txbox(s, x + Inches(0.35), top + Inches(0.28), cw - Inches(0.7),
              Inches(0.4), t, size=16, bold=True, color=color)
        tb = s.shapes.add_textbox(x + Inches(0.35), top + Inches(0.85),
                                  cw - Inches(0.7), Inches(3.1))
        tf = tb.text_frame
        tf.word_wrap = True
        first = True
        for it in items:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.line_spacing = 1.3
            p.space_after = Pt(8)
            r = p.add_run(); r.text = "· " + it
            r.font.size = Pt(14); r.font.color.rgb = INK; r.font.name = FONT


def section(num, title, sub, note):
    s = prs.slides.add_slide(BLANK)
    rect(s, Inches(0), Inches(0), W, H, fill=WHITE, shape=MSO_SHAPE.RECTANGLE)
    rect(s, Inches(0), Inches(0), Inches(0.22), H, fill=NAVY,
         shape=MSO_SHAPE.RECTANGLE)
    txbox(s, Inches(1.2), Inches(1.9), Inches(3.2), Inches(1.6),
          num, size=88, bold=True, color=NAVY_L)
    txbox(s, Inches(1.25), Inches(3.6), Inches(10.8), Inches(0.9),
          title, size=32, bold=True, color=NAVY)
    txbox(s, Inches(1.28), Inches(4.55), Inches(10.4), Inches(1.0),
          sub, size=16, color=MUTED, line=1.4)
    rect(s, Inches(1.28), Inches(4.32), Inches(1.1), Inches(0.05),
         fill=ACCENT, shape=MSO_SHAPE.RECTANGLE)
    s.notes_slide.notes_text_frame.text = note
    return s


def steps(s, items, top=Inches(1.95)):
    n = len(items)
    gap = Inches(0.22)
    total_w = Inches(11.6)
    cw = Emu(int((total_w - gap * (n - 1)) / n))
    for i, (num, title, sub) in enumerate(items):
        x = Inches(0.85) + Emu(int(i * (cw + gap)))
        rect(s, x, top, cw, Inches(3.0), fill=WHITE, line=LINE)
        rect(s, x, top, Inches(0.5), Inches(0.5), fill=NAVY,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
        txbox(s, x, top, Inches(0.5), Inches(0.5), num, size=16, bold=True,
              color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        txbox(s, x + Inches(0.14), top + Inches(0.62), cw - Inches(0.28),
              Inches(0.75), title, size=13.5, bold=True, color=INK, line=1.2)
        txbox(s, x + Inches(0.14), top + Inches(1.45), cw - Inches(0.28),
              Inches(1.4), sub, size=11, color=MUTED, line=1.28)


# ============ 1 封面 ============
s = prs.slides.add_slide(BLANK)
rect(s, Inches(0), Inches(0), W, H, fill=WHITE, shape=MSO_SHAPE.RECTANGLE)
rect(s, Inches(0), Inches(0), Inches(0.22), H, fill=NAVY, shape=MSO_SHAPE.RECTANGLE)
txbox(s, Inches(1.1), Inches(1.3), Inches(10.5), Inches(0.4),
      "并行与分布 · 课程报告", size=14, color=ACCENT, bold=True)
txbox(s, Inches(1.1), Inches(1.78), Inches(11.2), Inches(1.0),
      "用三台机器，守住五千块钱", size=38, bold=True, color=NAVY, line=1.25)
txbox(s, Inches(1.1), Inches(3.0), Inches(10.8), Inches(0.5),
      "——银行余额/转账场景下，分布式 KV Store 的设计与实现", size=17, color=MUTED)
rect(s, Inches(1.1), Inches(4.15), Inches(6.0), Inches(0.03), fill=LINE,
     shape=MSO_SHAPE.RECTANGLE)
txbox(s, Inches(1.1), Inches(4.42), Inches(10.6), Inches(1.2),
      "组员：__________　__________　__________\n"
      "代码仓库：https://github.com/L1tiansuo/distributed-kv-store",
      size=14, color=INK, line=1.6)
txbox(s, Inches(1.1), Inches(6.35), Inches(10.5), Inches(0.4),
      "三副本 · 单主复制 · 写需多数派落盘 · 读线性一致 · 转账原子 · 幂等去重",
      size=12, color=MUTED)
s.notes_slide.notes_text_frame.text = (
    "开场（约 40 秒，念慢一点）：\n"
    "「我们的作业是一个分布式 KV Store。这个题目听起来很抽象，所以我们给它找了一件特别具体的事：\n"
    "五个银行账户，一共五千块钱，让三台机器一起记账。\n"
    "我们要回答的问题只有一个：这三台机器里随便坏一台、网络随便断一下，这五千块钱会不会多一分、少一分？」\n"
    "说完停顿 2 秒，翻页。"
)
footer(s, 1, None)

# ============ 2 路线图 ============
s = slide_head("今天分四段，每段只回答一个问题", "一页看懂今天的结构")
seg = [
    ("01", "问题", "为什么一台机器\n靠不住？多台又难在哪？", "P3 – P7"),
    ("02", "机制", "我们的系统是怎么\n保证钱不丢的？", "P8 – P18"),
    ("03", "证据", "这些设计真的管用吗？\n六组实验全部真跑", "P19 – P26"),
    ("04", "反思", "踩了哪些坑，\n还有什么没做？", "P27 – P30"),
]
for i, (num, t, sub, pg) in enumerate(seg):
    x = Inches(0.85) + Emu(int(i * Inches(2.98)))
    rect(s, x, Inches(2.15), Inches(2.72), Inches(3.15), fill=WHITE, line=LINE)
    rect(s, x, Inches(2.15), Inches(2.72), Inches(0.06), fill=NAVY,
         shape=MSO_SHAPE.RECTANGLE)
    txbox(s, x + Inches(0.28), Inches(2.45), Inches(2.2), Inches(0.6),
          num, size=26, bold=True, color=ACCENT)
    txbox(s, x + Inches(0.28), Inches(3.12), Inches(2.2), Inches(0.5),
          t, size=19, bold=True, color=NAVY)
    txbox(s, x + Inches(0.28), Inches(3.75), Inches(2.2), Inches(1.0),
          sub, size=12, color=MUTED, line=1.3)
    txbox(s, x + Inches(0.28), Inches(4.85), Inches(2.2), Inches(0.3),
          pg, size=11, color=MUTED)
takeaway(s, "先听懂问题，再看懂机制，最后看数字；来不及全听，记住第四段就行")
s.notes_slide.notes_text_frame.text = (
    "这一页给听众地图，30 秒带过。\n"
    "「四段：先讲这个问题为什么难，再讲我们怎么解，然后放实验数据，最后是我们踩过的坑。\n"
    "如果中间走神了，记住最后一段的总结就行。」\n"
    "然后直接翻到下一页。"
)
footer(s, 2, None)

# ============ 3 一台机器的困境 ============
s = slide_head("钱存在一台电脑上，会出什么岔子", "从一个日常问题开始")
bullets(s, [
    ("五个账户：A 到 E，每人 1000 块，总额 5000", 0),
    ("这个总额 5000 就是我们整份作业的「验收线」", 1),
    ("一台机器记账，会发生三件事：", 0),
    ("机器宕机 → 账本打不开，钱「冻结」了", 1),
    ("硬盘损坏 → 账本没了，钱「蒸发」了", 1),
    ("程序出 bug → 数字错了，没人能对账", 1),
], size=17, gap=8)
takeaway(s, "一份数据只放在一台机器上，等于把鸡蛋放进一个篮子")
s.notes_slide.notes_text_frame.text = (
    "这一页把场景讲到每个人都能代入：\n"
    "「我们的系统就管一件事：五个人的余额。为什么选银行场景？因为它有一条铁律——\n"
    "五个人加起来必须永远是 5000。多一分，是印钱；少一分，是抢钱。\n"
    "后面所有实验，我们都拿这条线来验收。」\n"
    "接着说一台机器的三个下场，语气放轻松，这是共识，不需要论证。"
)
footer(s, 3, None)

# ============ 4 多副本的新麻烦 ============
s = slide_head("多存几份就好了吗？麻烦才刚开始", "自然想法的代价")
bullets(s, [
    ("自然想法：同一本账，三台机器各存一份", 0),
    ("一台挂了，另外两台还能干活 —— 可用性解决了", 1),
    ("但新问题立刻出现：三台机器上的数字，怎么保证一样？", 0),
    ("A 转了 B 一百块，机器 1 记了，机器 2 还没记，这时有人来机器 2 查余额", 1),
    ("网络慢一点、消息丢一条、机器慢半拍，三份账就开始对不上", 1),
], size=17, gap=8)
takeaway(s, "副本解决了「机器坏了」，却带来了「各说各话」")
s.notes_slide.notes_text_frame.text = (
    "先肯定直觉：多存几份，方向是对的，防的就是单点故障。\n"
    "然后转折：「但三台机器不是三台复印机——每次转账都要通知另外两台，\n"
    "通知的路上会出各种事。数字对不上，比机器坏了更麻烦，因为没人知道该信谁。」\n"
    "下一页把「对不上」具体化。"
)
footer(s, 4, None)

# ============ 5 四种丢钱方法 ============
s = slide_head("分布式系统有四种方法把钱搞丢", "问题清单，也是我们的验收清单")
rows = [
    ("① 假成功", "写入只落了一台就回复成功，这台随即宕机", "钱没了，但客户端以为成功了"),
    ("② 双主", "两台机器都以为自己是老大，各收各的写", "两份账越差越远"),
    ("③ 重复扣款", "客户端没收到回复，把同一笔转账又发一遍", "一次转账扣两次钱"),
    ("④ 读到旧值", "从还没追上的机器读余额", "余额「回到了过去」"),
]
add_table(s, ["出事方式", "怎么发生的", "后果"], rows, [2.2, 5.4, 4.0],
          top=Inches(1.95), size=14)
takeaway(s, "后面每一页设计，都是在堵这四个洞里的一个")
s.notes_slide.notes_text_frame.text = (
    "这一页是全场最重要的问题清单，讲慢一点，逐行讲：\n"
    "第一行「假成功」：回复了你成功，但数据只在一个地方，那个地方没了就什么都没了。\n"
    "第二行「双主」：两个节点都觉得轮到自己说了算，两边都在收钱，越收越乱。\n"
    "第三行最好理解：你没收到短信，会再发一遍；机器也一样，但银行不能扣两次。\n"
    "第四行：你查到的是旧数据，看着像钱回来了。\n"
    "收尾：「我们的设计就四件事，一件堵一个洞。」"
)
footer(s, 5, None)

# ============ 6 我们的答案 ============
s = slide_head("三副本、一个主、多数派，就这三句话", "我们的答案")
three = [
    ("1 个主", "leader", "所有写都交给它排队，\n避免「各说各话」"),
    ("多数派", "2 / 3 落盘", "写进两台才算成功，\n堵住「假成功」"),
    ("认主才读", "read-index", "读之前先确认自己\n还是主，堵「读到旧值」"),
]
metrics(s, three, top=Inches(1.95))
txbox(s, Inches(0.9), Inches(5.15), Inches(11.6), Inches(0.9),
      "第①②洞由「一个主 + 多数派」堵，第③洞由幂等堵，第④洞由「认主才读」堵",
      size=14, color=MUTED)
takeaway(s, "没有新发明：把每条规则都对应到一个会出事的场景")
s.notes_slide.notes_text_frame.text = (
    "用三句话概括全部设计，这是听众最该记住的一页：\n"
    "「第一句：只有一个主，所有写都到它那里排队。第二句：写进两台才算成功。\n"
    "第三句：读之前先问自己还是不是主。」\n"
    "然后指着下面一行小字，把上一页的四个洞连过来：\n"
    "前两句话堵前两个洞，第四个洞由第三句堵，第三个洞靠下一节的幂等。"
)
footer(s, 6, None)

# ============ 7 工程底牌 ============
s = slide_head("1500 行 Python，零第三方依赖", "工程底牌")
bullets(s, [
    "Python 3.13 标准库：socket、json、threading",
    "三个独立进程，真实 TCP 长连接",
    "日志先写盘再干活（WAL），断电可重放",
    "一把大锁 + Condition，不玩花式并发",
], y=Inches(1.95), size=18, gap=18)
s.notes_slide.notes_text_frame.text = (
    "「全部代码大概 1500 行，只用 Python 自带的东西，没装任何第三方库。\n"
    "为什么这么克制？因为这份作业的重点不是堆功能，是每一条规则都要能讲清楚为什么。\n"
    "代码越简单，被问住的概率越低。」\n"
    "如果老师问「为什么不用 gRPC/Redis」，就答：多一个依赖就多一个「为什么用它」的问题，标准库已经够用。"
)
footer(s, 7, None)

# ============ 8 章节页：机制 ============
s = section("02", "机制：系统怎么保证钱不丢",
        "五件事：写一笔钱的路径、谁说了算、读也要小心、\n同一笔别扣两次、断电之后",
        "过渡句：「设计只有三句话，但每句话背后都有一层机制。我们一层一层看。」\n"
        "语速放慢，从这一页开始进入技术部分。")
footer(s, 8, None)

# ============ 9 写路径 ============
s = slide_head("写一笔转账，4 毫秒里发生了什么", "机制一 · 写路径")
steps(s, [
    ("1", "客户端发来转账", "A 转 B 一百块，\n带一个唯一请求号"),
    ("2", "主节点写日志", "追加进自己的日志，\n立刻落盘 fsync"),
    ("3", "发给两个从节点", "同时发，不等回复\n就进入下一步"),
    ("4", "收到一个回话", "自己加一台从 = 多数派，\n这条日志可以提交了"),
    ("5", "两边都改", "余额落进账本，\n回复客户端成功"),
], top=Inches(1.9))
txbox(s, Inches(0.9), Inches(5.25), Inches(11.6), Inches(0.8),
      "关键：第 4 步只等「一台」回话 —— 三台里任意两台活着，写就能成功",
      size=14, color=MUTED)
takeaway(s, "「写成功」的真实含义：至少两台机器的硬盘里都有这笔账")
s.notes_slide.notes_text_frame.text = (
    "这一页是全片技术核心，按编号一步一步讲，讲完一步停半秒：\n"
    "「第一步，请求带一个编号，这个编号后面幂等要用。第二步，主节点先写进自己的日志并且落盘。\n"
    "第三步，把这条日志发给另外两台。第四步最关键：只等一台回话，加上自己就是两台——多数派。\n"
    "第五步才改余额、才回复成功。」\n"
    "最后强调：所以「写成功」不是客套话，它的意思是至少两台机器的硬盘里都有了。"
)
footer(s, 9, None)

# ============ 10 fsync ============
s = slide_head("一笔写 4.1 毫秒，其中 3.6 毫秒在等硬盘", "为什么慢也要落盘")
metrics(s, [
    ("4.1 ms", "单笔写延迟", "从客户端发出到\n收到成功回复"),
    ("3.6 ms", "花在 fsync 上", "把日志真正写进硬盘，\n而不只是内存"),
    ("6.5 倍", "关掉 fsync 的吞吐差", "253.8 → 1646.2 ops/s\n（我们默认开着）"),
], top=Inches(1.95))
txbox(s, Inches(0.9), Inches(5.15), Inches(11.6), Inches(0.9),
      "类比：fsync 就是「写下来才算数」——只在脑子里记住的承诺，断电就作废",
      size=14, color=MUTED)
takeaway(s, "钱的事不能用「可能」记账：宁可每笔慢 3.6 毫秒，不要「重启后看运气」")
s.notes_slide.notes_text_frame.text = (
    "用三个数字讲清楚我们把钱花在哪了：\n"
    "「一笔写总共 4.1 毫秒，其中 3.6 毫秒都在等硬盘说『我存好了』。\n"
    "如果这个等待省掉，速度能快 6.5 倍——我们测过，253 对 1646。\n"
    "但我们默认开着它，因为省掉的是速度，丢掉的是『重启之后数据还在』的保证。」\n"
    "有人问「为什么不是 100 倍」：因为硬盘其实很快，慢的是「等它确认」。"
)
footer(s, 10, None)

# ============ 11 选主 ============
s = slide_head("三台机器里谁说了算：投票选主", "机制二 · 选主")
bullets(s, [
    ("类比：小组作业选一个组长，组长失联了就重新选", 0),
    ("规则一：得票过半才当选 —— 三台里要拿两票", 1),
    ("规则二：每一轮选举有一个「任期号」，只增不减", 1),
    ("规则三：谁的日志更新，谁才有资格当选", 1),
    ("这套规则就是 Raft 的简化版，我们实现了投票、任期、日志新旧比较", 0),
], size=17, gap=8)
takeaway(s, "过半投票 → 任意时刻最多一个主；任期号 → 旧的命令自动失效")
s.notes_slide.notes_text_frame.text = (
    "第一次出现 Raft 这个词，先给直觉再报名字：\n"
    "「就像一个小组选一个组长：要过半数同意才算数，每一任有编号，越新的编号越大。\n"
    "老组长回来发号施令，大家一看编号过期，就不听他的了。」\n"
    "然后说：这套规则有个名字，叫 Raft，我们实现了它的核心部分。\n"
    "被问「为什么不用 Paxos」：Raft 就是为了「能讲明白」而生的，和我们这份作业的目标一致。"
)
footer(s, 11, None)

# ============ 12 旧主 ============
s = slide_head("如果旧主不知道自己下台了呢", "机制二补充 · 脑裂")
two_col(s,
        "会发生什么",
        ["旧主被网络隔开，它还以为自己是主",
         "新主已经在另一边当选，也在收写请求",
         "两个「主」同时存在 → 就是双主问题"],
        "为什么多数派能防住",
        ["旧主写日志需要「多数派确认」",
         "它被隔离，永远凑不齐两台",
         "所以旧主的写一条也提交不了"],
        left_color=RED, right_color=GREEN)
takeaway(s, "多数派是一票否决权：凑不齐人，就算你自称老大，也一笔记不进去")
s.notes_slide.notes_text_frame.text = (
    "这页回答上一页留下的疑问：\n"
    "「组长被关在门外了，他不知道屋里已经选出新组长，还在门口发号施令，怎么办？」\n"
    "答案就是多数派：他的每一条命令都需要「两台确认」，他被隔离，凑不齐，\n"
    "所以他的命令一条都不生效。\n"
    "预告：这个场景我们真做了实验，在第 22 页，quorum 改成 1 之后防线就没了。"
)
footer(s, 12, None)

# ============ 13 读路径 ============
s = slide_head("查个余额，为什么不能随便读", "机制三 · 读路径")
bullets(s, [
    ("直觉做法：随便找一台读 —— 不行", 0),
    ("从节点可能落后：转账刚在主机完成，它还没收到", 1),
    ("从「主节点」读就行吗 —— 也不一定", 0),
    ("它可能是刚被换掉的旧主，自己还不知道", 1),
    ("我们的做法 read-index：读之前，主节点先向多数派确认「我还是主」", 0),
    ("确认通过 + 本地数据已跟上 → 才返回余额", 1),
], size=17, gap=6)
takeaway(s, "读和写走同一条多数派防线，读到的每一笔都是已提交的")
s.notes_slide.notes_text_frame.text = (
    "「写要小心，读也一样。最容易想错的一句是：从主节点读不就行了？\n"
    "问题是，上一页那个被关门的旧组长，它也是主——旧的主。\n"
    "所以我们的读多了一个动作：先跟多数派对个暗号，确认自己还是现任，数据也没落后，\n"
    "才告诉你余额。这个读法叫 read-index，它保证你读到的每一个数都是「已提交」的。」"
)
footer(s, 13, None)

# ============ 14 脏读开关 ============
s = slide_head("我们故意留了一个「脏读」开关", "机制三 · 对照实验")
two_col(s,
        "开关打开（脏读）",
        ["跳过「确认还是主」这一步，直接读本地",
         "换主后的旧节点上：读到 1000",
         "新主上同一时刻：已经是 700"],
        "为什么要留着它",
        ["它能稳定复现「读到旧值」这个现象",
         "把抽象的一致性变成「能看到的差别」",
         "证明默认路径（线性读）确实在起作用"],
        left_color=RED, right_color=GREEN)
takeaway(s, "脏读不是 bug，是对照组。没有对照，就说不清默认路径保护了什么")
s.notes_slide.notes_text_frame.text = (
    "「我们代码里留了一个开关，打开它就退回到「随便读」。\n"
    "留着它不是为了耍酷：实验五 D 段里，同一时刻旧主脏读返回 1000，新主返回 700。\n"
    "没有这个对照，光说『我们的读是一致的』是空的；有了它，差别一眼就能看见。\n"
    "默认路径永远是关着开关的，开关只在实验里用。」"
)
footer(s, 14, None)

# ============ 15 重复扣款 ============
s = slide_head("没收到回复，你会再发一遍；机器也会", "机制四 · 重复扣款")
bullets(s, [
    ("真实场景：请求执行了，但回复在网络里丢了", 0),
    ("客户端只能看到「没成功」，于是重试 —— 这是对的", 1),
    ("但没有保护的话：同一笔转账被执行两次，扣两次钱", 1),
    ("这是分布式系统里最经典、也最容易翻车的事故", 0),
    ("我们的要求：同一个请求来多少次，都只生效一次 —— 这叫「幂等」", 0),
], size=17, gap=8)
takeaway(s, "「重试」是客户端的本能，「只生效一次」必须是服务端的保证")
s.notes_slide.notes_text_frame.text = (
    "这一页先从生活经验讲起：\n"
    "「你转账没收到短信，会再转一次吗？会的。客户端也一样。\n"
    "问题不在重试——重试是对的，问题在服务端得认出『这一笔你来过了』。」\n"
    "引出术语：这个性质叫幂等。白话：来几次，都按一次算。"
)
footer(s, 15, None)

# ============ 16 两层去重 ============
s = slide_head("两层去重：记性好的快，记性差的稳", "机制四 · 怎么做到幂等")
two_col(s,
        "快路径：主节点内存表",
        ["每个请求有唯一编号 req_id",
         "见过这个编号 → 直接返回第一次的结果",
         "快，但换主之后这张表就没了"],
        "慢路径：账本里的去重表",
        ["去重记录跟着日志复制到每台机器",
         "换主之后，新主也认得这个编号",
         "代价：每次写都要带着它，多一点点开销"],
        left_color=NAVY, right_color=GREEN)
takeaway(s, "幂等不是「记住请求」，是让第二次来的人，看到第一次的结果")
s.notes_slide.notes_text_frame.text = (
    "「两层：主节点脑子里记一份（快），账本里再记一份（稳）。\n"
    "为什么要两层？因为换主的时候，脑子里的那份会跟着旧主一起消失。\n"
    "只有写进账本、跟着日志复制走的那份，换完主还能认出来。\n"
    "注意第二层的返回不是『报个错说你重复了』，而是把第一次的结果原样再给你一次——\n"
    "实验三里能看到，后两次返回的是 duplicate: true，但余额一模一样。」"
)
footer(s, 16, None)

# ============ 17 原子性 ============
s = slide_head("A 转 B 一百块，两边要么都改、要么都不改", "机制五 · 原子性")
two_col(s,
        "常规做法：两阶段提交",
        ["先问两边「准备好没有」，再统一落笔",
         "协议复杂，还要处理协调者宕机",
         "我们一行没写"],
        "我们的做法：一条日志项",
        ["把「A-100、B+100」写进同一条日志",
         "日志项要么应用、要么不应用",
         "原子性由日志天然保证"],
        left_color=MUTED, right_color=GREEN)
takeaway(s, "用日志项的原子性，换掉了整个事务协议，这是省掉代码最多的一页")
s.notes_slide.notes_text_frame.text = (
    "「跨账户转账要原子：A 扣了 B 没加，就是印钱事故。\n"
    "教科书做法是两阶段提交，我们没用。\n"
    "因为转账的两个动作本来就可以写进同一条日志，而日志要么整体生效、要么整体不生效。\n"
    "把问题挪了个位置：从『怎么协调两个账户』变成『怎么写好一条日志』，后者我们已经有答案了。」"
)
footer(s, 17, None)

# ============ 18 持久化 ============
s = slide_head("断电之后：先写日志，再干活", "机制六 · 持久化")
bullets(s, [
    ("WAL：任何改动先追加进日志文件 log.jsonl，再改账本", 0),
    ("重启时从头重放日志，账本原样恢复", 1),
    ("任期、投票记录必须 fsync —— 记错会出双主", 1),
    ("提交进度只 flush 不 fsync —— 丢了能从日志重算", 1),
    ("实测：容器整个杀掉再启动，305 条日志全部重放，数据完整", 0),
], size=17, gap=8)
takeaway(s, "凡是「不能从别处算出来」的状态才 fsync，能算出来的就不浪费这 3.6 毫秒")
s.notes_slide.notes_text_frame.text = (
    "「持久化的核心动作叫 WAL：先写日志，再干活。\n"
    "就像你先记账再花钱，断电了翻账本就能补齐。\n"
    "有个细节能看出取舍：任期和投票必须立刻落盘，因为记错了会出两个主；\n"
    "而提交进度不用，因为它能从日志重新算出来。\n"
    "这个『什么必须落盘、什么可以偷懒』的判断，就是第 10 页那 3.6 毫秒该花在哪儿的答案。」"
)
footer(s, 18, None)

# ============ 19 章节页：证据 ============
s = section("03", "证据：这些设计真的管用吗",
        "不做模拟。三个真实进程、真实网络、真实落盘，\n六组实验，每组三轮取中位数",
        "过渡句：「前面说的都是设计，设计说得再好也得跑一遍才知道。\n"
        "接下来六组实验，每一组都是真跑出来的。」")
footer(s, 19, None)

# ============ 20 实验方法 ============
s = slide_head("实验怎么做，结果才作数", "实验方法")
bullets(s, [
    ("三个真实进程，不是模拟器；真实 TCP，真实 fsync", 0),
    ("每组实验跑 3 轮取中位数，先热身再计时", 1),
    ("只轮询活着的进程 —— 不然测出来的是超时，不是选主速度", 1),
    ("客户端复用连接 —— 不然测出来的是建连开销，不是写延迟", 1),
    ("全部原始数据在仓库 results/*.json，随时可复算", 0),
], size=17, gap=8)
takeaway(s, "我们花了一半力气让测量本身不撒谎，后面每个数字都经得起复现")
s.notes_slide.notes_text_frame.text = (
    "「先说方法，再说数据，因为方法不对，数据就是假的。\n"
    "举两个真实的教训：一开始我们测出来的写延迟带着『每次新建连接』的开销，\n"
    "测出来的选主时间带着『等死进程超时』的等待。这两个坑修掉之后，数字才可信。\n"
    "所有原始数据都在仓库的 results 目录里，谁都可以拿去复算。」"
)
footer(s, 20, None)

# ============ 21 实验一 ============
s = slide_head("杀掉主节点五轮，数据一次都没丢", "实验一 · 故障转移")
add_table(s, ["轮次", "选主耗时", "说明"],
          [("1", "1075 ms", "一个落后节点白投了自己一票，多花了一个选举超时"),
           ("2", "527 ms", ""),
           ("3", "480 ms", ""),
           ("4", "390 ms", ""),
           ("5", "436 ms", "")],
          [1.6, 2.2, 7.8], top=Inches(1.9), size=14)
takeaway(s, "问题不是会不会丢，是多久恢复：半秒上下，数据零丢失")
s.notes_slide.notes_text_frame.text = (
    "「五轮实测，把主节点直接杀掉，看多久选出新主。\n"
    "第一轮最慢，1075 毫秒——原因我们也查了：一个日志落后的节点先给自己投了一票，\n"
    "选不上，白等了一个超时。后面四轮稳定在半秒上下。\n"
    "这五轮里，总额始终是 5000，一笔都没丢。\n"
    "被问『第一轮为什么慢』是好事，说明老师在跟着看——如实讲就行。」"
)
footer(s, 21, None)

# ============ 22 实验二 ============
s = slide_head("多数派从 2 改成 1，一条写「蒸发」了", "实验二 · 脑裂")
two_col(s,
        "改了什么",
        ["把「写要两台确认」改成「一台就算数」",
         "然后制造网络分区：一边一台，一边两台",
         "两边各自都接受了写入，都回了「成功」"],
        "发生了什么",
        ["恢复网络后，少数派一侧被整体覆盖",
         "「订单-001」这条写，从账本上消失了",
         "客户端当初收到的可是「成功」"],
        left_color=MUTED, right_color=RED)
takeaway(s, "quorum=1 换来的是分区时还能写，丢掉的是「写成功」这三个字的分量")
s.notes_slide.notes_text_frame.text = (
    "「这是全场最有戏剧性的一组：把多数派要求从 2 改成 1，再断网。\n"
    "两边都能写，两边都说成功。网一恢复，一边的数据被另一边整个盖掉，\n"
    "那条『订单-001』就凭空消失了——可客户端当时收到的是成功。\n"
    "这就是为什么第 6 页说写要两台：不是为了快，是为了『说出去的话不能不算数』。」"
)
footer(s, 22, None)

# ============ 23 实验三 ============
s = slide_head("同一笔转账连发三次，只扣了一次", "实验三 · 幂等")
metrics(s, [
    ("3 次", "同一个 req_id 连发", "模拟客户端重试，\n含一次「回复丢了」"),
    ("1 次", "实际生效", "A 只被扣了一次 100，\n后两次返回原结果"),
    ("5000", "总额不变", "任何时刻对账，\n都是 5000"),
], top=Inches(1.95))
txbox(s, Inches(0.9), Inches(5.15), Inches(11.6), Inches(0.9),
      "后两次的返回里是 duplicate: true —— 不是报错，是把第一次的结果原样再给一次",
      size=14, color=MUTED)
takeaway(s, "客户端可以放心重试，这就是幂等两个字值多少钱的现场报价")
s.notes_slide.notes_text_frame.text = (
    "「用同一个请求编号连发三次，其中一次故意让回复丢在路上。\n"
    "结果：只扣了一次钱，后两次服务端返回的是第一次的结果，标着 duplicate。\n"
    "这页配合第 16 页的两层去重讲：快路径认出重复，慢路径保证换主之后还认得。\n"
    "一句话收：客户端随便重试，服务端保证只算一次。」"
)
footer(s, 23, None)

# ============ 24 实验四 ============
s = slide_head("题目里列的故障，一个个打上去", "实验四 · 故障清单")
add_table(s, ["注入的故障", "现象", "结果"],
          [("消息延迟 10 秒", "心跳堵在路上，从节点超时", "换主，新主用空操作追平旧日志"),
           ("消息重复 ×3", "同一条日志到达三遍", "去重表生效，只应用一次"),
           ("时钟拨回 60 秒", "时间戳乱了", "定序靠任期和日志下标，不受影响"),
           ("网络分区 1|2", "旧主被孤立", "旧主拒写，多数派一侧照常服务")],
          [3.0, 4.2, 4.4], top=Inches(1.9), size=13)
takeaway(s, "每条故障都提前写了预期，然后现象、数据逐条对上")
s.notes_slide.notes_text_frame.text = (
    "「题目的故障清单九条，我们挑了代表性的注入。\n"
    "注意第三行：把时钟拨回一分钟，系统毫无反应——\n"
    "因为我们的排序从来不看钟表，只看任期号和日志下标，这两个数只增不减。\n"
    "这就是老师那个问题『为什么不能只用物理时钟』的实验版答案。」"
)
footer(s, 24, None)

# ============ 25 实验五 ============
s = slide_head("这套设计的代价，都花在了看得见的地方", "实验五 · 代价")
add_table(s, ["代价项", "数字", "说明"],
          [("fsync 落盘", "253.8 → 1646.2 ops/s", "关掉落盘快 6.5 倍，我们默认开"),
           ("单主串行", "360 ≈ 374 ops/s", "热点单 key 和多 key 一样快——瓶颈在日志串行，不在锁"),
           ("容器部署", "183 vs 355 ops/s", "比裸进程慢一半，多的是端口映射那一跳，不是实现")],
          [2.6, 3.4, 5.6], top=Inches(1.9), size=13)
takeaway(s, "性能的上限不是我们没优化，是「强一致 + 单主」这个选择本身的价签")
s.notes_slide.notes_text_frame.text = (
    "「三笔账：第一笔，落盘占掉大部分吞吐，这是安全的价。\n"
    "第二笔，写热点账户和写不同账户一样快，说明瓶颈不在锁竞争，在日志本身要排队。\n"
    "第三笔，放容器里跑慢一半，但我们查过，慢在 Windows 的端口映射，不在实现。\n"
    "所以性能的天花板不是『没写好』，是我们选的那三句话自带的价签——这一点敢认。」"
)
footer(s, 25, None)

# ============ 26 数字总结 ============
s = slide_head("六组实验，记住这四个数就够", "一屏数字总结")
metrics(s, [
    ("0", "数据丢失", "五轮杀主、一次脑裂演练、\n全部实验，零丢失"),
    ("390ms", "最快选主", "五轮中最快一次；\n最慢 1075ms 也如实记录"),
    ("3发1扣", "幂等", "同一请求发三次，\n只扣一次钱"),
    ("6.5×", "落盘的价", "fsync 开关的吞吐差，\n我们选慢的那个"),
], top=Inches(1.95))
txbox(s, Inches(0.9), Inches(5.2), Inches(11.6), Inches(0.9),
      "还有一条永远成立的底线：五个账户，总额恒为 5000",
      size=15, color=NAVY, bold=True)
takeaway(s, "如果今天只带走一句话：总额 5000，从头到尾，一分没差")
s.notes_slide.notes_text_frame.text = (
    "「四个数：零丢失、最快半秒选主、三发一扣、落盘值六倍速。\n"
    "最后一个六倍要说清楚方向——我们选的是慢的那边，因为快的那边不保证重启后钱还在。\n"
    "下面那行大字再念一遍：总额 5000，从头到尾，一分没差。」"
)
footer(s, 26, None)

# ============ 27 章节页：反思 ============
s = section("04", "反思：比结果更重要的是过程",
        "四个真实的坑，和我们想清楚之后才\n决定不做的四件事",
        "过渡句：「最后一段，讲点结果之外的东西：我们修过的 bug，和主动放弃的功能。」")
footer(s, 27, None)

# ============ 28 踩坑 ============
s = slide_head("四个坑，每个都教会我们一件事", "踩坑记录")
add_table(s, ["坑", "现象", "修法"],
          [("结果发错了人", "换主后客户端收到空操作的结果", "等待项绑定到具体日志，不再按下标认领"),
           ("写要等 100ms", "只有心跳才复制日志", "有新日志立刻发，4ms 搞定"),
           ("定时落盘卡写", "每 200ms 一次 fsync，p99 飙到 63ms", "定时保存只 flush 不 fsync，降到 9ms"),
           ("连上了旧进程", "Windows 下端口被旧进程占用", "换独占模式 + 启动前清理残留")],
          [2.8, 4.4, 4.6], top=Inches(1.9), size=13)
takeaway(s, "每个坑都始于一个「以为对了」，这比「我们实现了 Raft」更能说明真的做过")
s.notes_slide.notes_text_frame.text = (
    "「四个都是真 bug。挑第一个细讲：换主的时候，客户端等的那条日志被新的空操作顶掉了，\n"
    "客户端收到的就是空操作的结果——钱其实没转，客户端却以为转了。\n"
    "修法是等结果的时候认准那一条日志本身，不再按位置认领。\n"
    "这段不用背，挑一个自己印象最深的讲，真实感比完整性重要。」"
)
footer(s, 28, None)

# ============ 29 没做什么 ============
s = slide_head("我们知道自己没做什么，也知道为什么", "不足与边界")
two_col(s,
        "没做的",
        ["pre-vote（防落后节点白拉票）",
         "日志快照（日志长了要压缩）",
         "成员变更（在线加机器）",
         "多主与跨地域低延迟写"],
        "为什么不做",
        ["第一轮的 1075ms 就是代价，我们如实记录",
         "五账户用不上，但知道该在哪加",
         "三节点够用，协议要复杂得多",
         "选了单主，就接受这个天花板"],
        left_color=MUTED, right_color=NAVY)
takeaway(s, "没做的每一件都答得出为什么，这份清单本身就是设计的一部分")
s.notes_slide.notes_text_frame.text = (
    "「最后主动交代没做什么：pre-vote、快照、成员变更、多主。\n"
    "每一条都说得出为什么不做的理由，而不是『来不及』。\n"
    "比如 pre-vote：第 21 页第一轮的 1075 毫秒就是它要解决的问题，\n"
    "我们没做，但把代价如实摆在数据里了。\n"
    "这页的心态是：主动暴露边界，比被问出来体面得多。」"
)
footer(s, 29, None)

# ============ 30 收尾 ============
s = prs.slides.add_slide(BLANK)
rect(s, Inches(0), Inches(0), W, H, fill=WHITE, shape=MSO_SHAPE.RECTANGLE)
rect(s, Inches(0), Inches(0), Inches(0.22), H, fill=NAVY, shape=MSO_SHAPE.RECTANGLE)
txbox(s, Inches(1.1), Inches(1.15), Inches(10.5), Inches(0.4),
      "一句话总结", size=14, color=ACCENT, bold=True)
txbox(s, Inches(1.1), Inches(1.7), Inches(11.2), Inches(2.0),
      "三副本、一个主、多数派落盘、幂等去重——\n选了单主，就接受单主的天花板；\n这些权衡不是没做好，是这个样子本来就要付的价。",
      size=26, bold=True, color=NAVY, line=1.5)
rect(s, Inches(1.1), Inches(4.35), Inches(6.0), Inches(0.03), fill=LINE,
     shape=MSO_SHAPE.RECTANGLE)
txbox(s, Inches(1.1), Inches(4.62), Inches(10.8), Inches(1.4),
      "答辩问题对应页：版本比较→P11　写成功含义→P9/P10　读到旧值→P13/P14\n"
      "quorum=1→P22　物理时钟→P24　失败请求→P15/P16",
      size=13, color=MUTED, line=1.55)
txbox(s, Inches(1.1), Inches(6.0), Inches(10.8), Inches(0.9),
      "代码仓库：https://github.com/L1tiansuo/distributed-kv-store\n"
      "谢谢，请老师提问。",
      size=14, color=INK, line=1.6)
s.notes_slide.notes_text_frame.text = (
    "收尾停在这三句话上，不要说「我们的系统还不完善」这种自我否定的话。\n"
    "改成：「每个是都对应一个不，我们知道自己选了什么、放弃了什么。」\n"
    "然后请老师提问。屏幕上那两行「问题对应页」是给自己看的提词器——\n"
    "老师问到哪个问题，就翻到那一页，指着数据回答。"
)
footer(s, 30, None)

out = os.path.join(ROOT, "ppt", "分布式KV Store 讲解_v2.pptx")
os.makedirs(os.path.dirname(out), exist_ok=True)
prs.save(out)
print("已生成：", out, "共", len(prs.slides._sldIdLst), "页")
