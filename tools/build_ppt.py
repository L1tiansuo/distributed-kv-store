#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成讲解用 PPT。每页都写好了备注（讲稿），照着念也不会卡。"""
import json
import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIG = os.path.join(ROOT, "docs", "figures")

INK = RGBColor(0x1C, 0x22, 0x33)
MUTED = RGBColor(0x68, 0x70, 0x8A)
BLUE = RGBColor(0x2F, 0x6B, 0xFF)
BLUE_L = RGBColor(0xEA, 0xF0, 0xFF)
GRAY_L = RGBColor(0xF4, 0xF6, 0xFB)
LINE = RGBColor(0xD8, 0xDD, 0xEA)
GREEN = RGBColor(0x12, 0xA0, 0x5C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xD9, 0x43, 0x3D)

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


def rect(slide, x, y, w, h, fill=BLUE_L, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
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
    if kicker:
        txbox(s, Inches(0.85), Inches(0.52), Inches(11), Inches(0.3), kicker,
              size=12, color=BLUE, bold=True)
        txbox(s, Inches(0.85), Inches(0.82), Inches(11.6), Inches(0.6), title,
              size=27, bold=True)
    else:
        txbox(s, Inches(0.85), Inches(0.62), Inches(11.6), Inches(0.7), title,
              size=28, bold=True)
    rect(s, Inches(0.85), Inches(1.5), Inches(0.72), Inches(0.045), fill=BLUE,
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


def add_image(s, name, top=Inches(1.75), height=None, caption=""):
    path = os.path.join(FIG, name)
    if height:
        pic = s.shapes.add_picture(path, Inches(0), top, height=height)
    else:
        pic = s.shapes.add_picture(path, Inches(0), top, width=Inches(10.6))
    pic.left = Emu(int((W - pic.width) / 2))
    if caption:
        txbox(s, Inches(0.85), pic.top + pic.height + Inches(0.12), Inches(11.6),
              Inches(0.3), caption, size=11, color=MUTED, align=PP_ALIGN.CENTER)
    return pic


def add_table(s, headers, rows, col_w, top=Inches(1.9), size=13, header_size=13,
              first_col_bold=False):
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
        cell.fill.fore_color.rgb = BLUE_L
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = h
        r.font.size = Pt(header_size); r.font.bold = True
        r.font.color.rgb = INK; r.font.name = FONT
    for ri, row in enumerate(rows, start=1):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.text = ""
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if ri % 2 else GRAY_L
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.06)
            p = cell.text_frame.paragraphs[0]
            pure_num = not any('\u4e00' <= ch <= '\u9fff' for ch in str(val))
            p.alignment = (PP_ALIGN.CENTER if (headers[ci] == "#" or
                                              (pure_num and len(str(val)) <= 8))
                           else PP_ALIGN.LEFT)
            r = p.add_run(); r.text = str(val)
            r.font.size = Pt(size); r.font.color.rgb = INK; r.font.name = FONT
            r.font.bold = first_col_bold and ci == 0
    # 去掉默认表格样式的强烈配色影响：设置边框为浅灰
    for ri in range(len(rows) + 1):
        for ci in range(len(headers)):
            cell = tbl.cell(ri, ci)
            cell.text_frame.word_wrap = True
    return tbl


def metrics(s, items, top=Inches(2.05), note=""):
    n = len(items)
    gap = Inches(0.32)
    total_w = Inches(11.6)
    cw = Emu(int((total_w - gap * (n - 1)) / n))
    for i, (num, label, sub) in enumerate(items):
        x = Inches(0.85) + Emu(int(i * (cw + gap)))
        rect(s, x, top, cw, Inches(2.78), fill=WHITE, line=LINE)
        rect(s, x, top, cw, Inches(0.06), fill=BLUE, shape=MSO_SHAPE.RECTANGLE)
        txbox(s, x + Inches(0.3), top + Inches(0.38), cw - Inches(0.5),
              Inches(0.8), num, size=34, bold=True, color=BLUE)
        txbox(s, x + Inches(0.3), top + Inches(1.22), cw - Inches(0.5),
              Inches(0.42), label, size=14, bold=True, color=INK)
        txbox(s, x + Inches(0.3), top + Inches(1.68), cw - Inches(0.5),
              Inches(0.95), sub, size=11, color=MUTED, line=1.25)


def two_col(s, left_title, left_items, right_title, right_items,
            left_color=BLUE, right_color=GREEN, top=Inches(1.9)):
    cw = Inches(5.6)
    for i, (t, items, color) in enumerate(((left_title, left_items, left_color),
                                          (right_title, right_items, right_color))):
        x = Inches(0.85) + Emu(int(i * (cw + Inches(0.4))))
        rect(s, x, top, cw, Inches(4.35), fill=WHITE, line=LINE)
        txbox(s, x + Inches(0.35), top + Inches(0.28), cw - Inches(0.7),
              Inches(0.4), t, size=16, bold=True, color=color)
        tb = s.shapes.add_textbox(x + Inches(0.35), top + Inches(0.85),
                                  cw - Inches(0.7), Inches(3.3))
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


# ============ 1 封面 ============
s = prs.slides.add_slide(BLANK)
rect(s, Inches(0), Inches(0), W, H, fill=WHITE, shape=MSO_SHAPE.RECTANGLE)
rect(s, Inches(0), Inches(0), Inches(0.22), H, fill=BLUE, shape=MSO_SHAPE.RECTANGLE)
txbox(s, Inches(1.1), Inches(1.35), Inches(10.5), Inches(0.4),
      "并行与分布 · 课程报告", size=14, color=BLUE, bold=True)
txbox(s, Inches(1.1), Inches(1.78), Inches(10.8), Inches(1.9),
      "在特定负载与故障模型下\n设计一个 KV Store", size=36, bold=True, line=1.32)
txbox(s, Inches(1.1), Inches(3.62), Inches(10.8), Inches(0.5),
      "——银行余额/转账场景：强一致、幂等、多数派提交的取舍", size=17, color=MUTED)
rect(s, Inches(1.1), Inches(4.32), Inches(6.0), Inches(0.03), fill=LINE,
     shape=MSO_SHAPE.RECTANGLE)
txbox(s, Inches(1.1), Inches(4.6), Inches(10.6), Inches(1.2),
      "组员：__________　__________　__________\n"
      "代码仓库：https://github.com/<你的用户名>/distributed-kv-store",
      size=14, color=INK, line=1.6)
txbox(s, Inches(1.1), Inches(6.45), Inches(10), Inches(0.4),
      "三副本 · 单主复制 · 写需多数派落盘 · 读线性一致 · 网页可现场注入故障",
      size=12, color=MUTED)
s.notes_slide.notes_text_frame.text = (
    "开场 30 秒：我们选的是题目里的第二个场景——银行余额与转账。\n"
    "一句话讲清楚我们做了什么：三个副本，单主复制，写要两个节点落盘才算成功，读走线性一致，"
    "转账要么两边都改要么都不改，重复请求只生效一次。\n"
    "首页放了 GitHub 链接（作业要求），演示时可以先点开仓库再讲。"
)
footer(s, 1, None)

# ============ 2 这道题在考什么 ============
s = slide_head("这道题真正考的是那 6 个提问", "先看清评分标准，再谈设计")
bullets(s, [
    ("老师那页「典型提问」，就是我们设计的验收清单：", 0),
    ("版本比较代码删掉会怎样 → 日志冲突处理", 1),
    ("写成功代表几个节点已保存 → 多数派语义", 1),
    ("哪段代码能让客户端读到旧值 → 读路径", 1),
    ("quorum 从 2 改成 1 失去什么 → 容错与脑裂", 1),
    ("为什么不能只用物理时钟 → 定序方式", 1),
    ("失败请求的 happens-before → 幂等与重试", 1),
    ("所以我们没追求功能多，而是要求每一行都能说出「为什么」和「不这样会怎样」。", 0),
], size=17, gap=6)
s.notes_slide.notes_text_frame.text = (
    "这一页是先立规矩：告诉老师我们知道评分点在哪儿。\n"
    "左边六条就是老师 PPT 上的六个问题，右边是我们对应的设计点。\n"
    "话术：我们做题时把这一页当成验收清单，每一条都能在代码里指出来。"
)
footer(s, 2, None)

# ============ 3 选题理由 ============
s = slide_head("八个场景里，为什么挑银行", "选场景就是选「能不能自证正确」")
two_col(s,
        "被我们否掉的三个",
        ["购物车 CRDT：合并写得出来，但「合对了」很难当场证明",
         "游戏排行榜：实现最轻，可它答不上 quorum、线性读、版本比较",
         "配置中心：实验只能测「推送延迟几毫秒」，数字不直观"],
        "银行余额的两个好处",
        ["有一条能用数字说话的不变式：5 个账户总额恒等于 5000",
         "每一类错误都会让这个数字变——算错、重复扣、脑裂覆盖，全都藏不住",
         "顺带把共识、幂等、CAS 全用上，正好是这门课的主线"],
        left_color=MUTED, right_color=GREEN)
s.notes_slide.notes_text_frame.text = (
    "如果被问「为什么不做 CRDT/多主」：不是不会，是银行场景里「两个人同时改同一个余额」"
    "没有业务上合理的合并规则，总不能把两次扣款加起来。单主把冲突消灭在发生之前。\n"
    "强调不变式：总额 5000。这是我们全部实验的裁判。"
)
footer(s, 3, None)

# ============ 4 架构 ============
s = slide_head("系统结构：三个副本，一个主", "1500 行 Python，零第三方依赖")
add_image(s, "fig_arch.png", top=Inches(1.62), height=Inches(4.55),
          caption="节点间只有四种报文：拉票、追加日志、客户端请求、状态查询")
s.notes_slide.notes_text_frame.text = (
    "讲图的时候按编号走：① 客户端把转账发给 leader；② leader 追加日志并复制给两个 follower；"
    "③ follower 落盘后回确认；④ 拿到两个确认就提交；⑤ 状态机按顺序应用，一笔转账同时改两个账户；⑥ 回结果。\n"
    "为什么三个节点：多数派是 2，容忍挂一个，正好覆盖题目的故障深度；五个节点只是更慢。"
)
footer(s, 4, None)

# ============ 5 一次转账 ============
s = slide_head("一次转账，4 毫秒里发生了什么", "答辩最容易被追问的一条路径")
steps = [
    ("①", "客户端带 req_id 发给 leader", "leader 地址是缓存的，只有失效才重新探测"),
    ("②", "查幂等表（快路径）", "命中就直接返回上次结果，日志都不增长"),
    ("③", "追加日志 + fsync", "约 3.6 ms，是单笔延迟的主要成分"),
    ("④", "复制到 follower，拿多数派", "有未复制的日志就立刻发，不等 100ms 心跳"),
    ("⑤", "提交后立刻应用状态机", "扣一边、加一边、版本各 +1、记幂等表"),
    ("⑥", "把业务结果回给客户端", "返回的是「转账成功/余额不足」，不是「我写进日志了」"),
]
y = Inches(1.75)
for i, (num, title, sub) in enumerate(steps):
    rect(s, Inches(0.85), y, Inches(0.52), Inches(0.52), fill=BLUE,
         shape=MSO_SHAPE.OVAL)
    txbox(s, Inches(0.85), y + Inches(0.07), Inches(0.52), Inches(0.4), num,
          size=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    txbox(s, Inches(1.55), y + Inches(0.02), Inches(4.3), Inches(0.4), title,
          size=15, bold=True)
    txbox(s, Inches(5.9), y + Inches(0.05), Inches(6.5), Inches(0.4), sub,
          size=12.5, color=MUTED)
    y += Inches(0.82)
s.notes_slide.notes_text_frame.text = (
    "这一页是全场的技术核心，慢一点讲。\n"
    "关键点：第 3 步的 fsync 决定了 4 ms 的延迟；第 5 步「提交即应用」是我们踩坑后改的，"
    "原来只在定时器里应用，白等 20 ms。\n"
    "如果被问「写成功到底几个节点存了」：两个，含 leader 自己，而且两个都 fsync 到了磁盘。"
)
footer(s, 5, None)

# ============ 6 三个关键决策 ============
s = slide_head("八个决策里的三个关键", "每一个「是」都对应一个「不」")
cards = [
    ("单主复制", "不做多主",
     "多主要处理写冲突，而「两次扣款」没有合理的合并规则。把冲突消灭在发生之前。"),
    ("quorum = 2/3", "挂两个就不能写",
     "挂一个仍可写；改成 1 会脑裂。实验里 quorum=1 直接吞掉了一笔已回「成功」的转账。"),
    ("一条日志项 = 一笔转账", "不支持跨分片大事务",
     "复制日志本身就是事务日志，原子性免费；因此不需要两阶段提交。"),
]
cw = Inches(3.72)
for i, (t, sub, body) in enumerate(cards):
    x = Inches(0.85) + Emu(int(i * (cw + Inches(0.24))))
    rect(s, x, Inches(1.9), cw, Inches(3.9), fill=WHITE, line=LINE)
    rect(s, x, Inches(1.9), cw, Inches(0.055), fill=BLUE, shape=MSO_SHAPE.RECTANGLE)
    txbox(s, x + Inches(0.32), Inches(2.18), cw - Inches(0.6), Inches(0.5), t,
          size=18, bold=True)
    txbox(s, x + Inches(0.32), Inches(2.72), cw - Inches(0.6), Inches(0.4),
          "放弃：" + sub, size=12, color=RED, bold=True)
    txbox(s, x + Inches(0.32), Inches(3.22), cw - Inches(0.6), Inches(2.3), body,
          size=13, color=INK, line=1.45)
txbox(s, Inches(0.85), Inches(6.0), Inches(11.6), Inches(0.6),
      "另外五个：幂等表放状态机、读走 read-index、用（任期，下标）定序、不分片、不做快照/成员变更/pre-vote。",
      size=12.5, color=MUTED)
s.notes_slide.notes_text_frame.text = (
    "三个决策对应三张底牌：单主（消灭冲突）、quorum=2（要容错）、日志即事务（省掉 2PC）。\n"
    "每个都说清楚「放弃了什么」，因为作业要的就是取舍。\n"
    "下面那行是另外五个，可以一句话带过，被问再展开。"
)
footer(s, 6, None)

# ============ 7 原子性 ============
s = slide_head("转账跨两个账户，怎么保证原子", "我们没用两阶段提交，一行代码也没写")
two_col(s,
        "方案 A：两阶段提交（我们没用）",
        ["要写协调者、准备/提交两个阶段、超时回滚",
         "协调者宕机 → 参与者锁悬挂，要额外一套恢复逻辑",
         "两份日志、两次落盘，延迟翻倍"],
        "方案 B：一条日志项 = 一笔事务（我们用了）",
        ["日志项里同时写 from/to/amount，在状态机里一起改",
         "要么整条应用，要么整条不应用 —— 由「按顺序确定性执行」保证",
         "换主、截断、重放，都只有「整条」这一种粒度"],
        left_color=RED, right_color=GREEN)
s.notes_slide.notes_text_frame.text = (
    "如果被问「为什么不用 2PC」：2PC 是给多个独立分片用的，我们只有一个状态机，用不上。\n"
    "而且 2PC 会引入协调者宕机、锁悬挂这些新问题——作业里没要求，加了只会增加被问倒的面积。\n"
    "注意：这条决策成立的前提是「不做分片」。一旦分片，跨片转账就绕不开 2PC 或类似机制。"
)
footer(s, 7, None)

# ============ 8 读路径 ============
s = slide_head("读：为什么不能直接读 leader", "同一时刻，两个读返回不同的值")
add_table(s,
          ["读法", "做什么", "结果", "代价"],
          [["stale（脏读）", "直接取本地已应用的值", "返回 1000（旧值）", "0 次往返"],
           ["linearizable（默认）", "先拿多数派心跳确认自己还是 leader", "返回 700（新值）", "1 个 RTT"],
           ["孤主上的线性读", "拿不到多数派", "3 秒后拒答 timeout_read", "等待 3 s"]],
          [2.6, 4.5, 3.2, 1.9], top=Inches(1.95), size=13)
txbox(s, Inches(0.85), Inches(4.05), Inches(11.6), Inches(1.6),
      "一个被分区的旧 leader，自己并不知道已经被换掉了。它本地的值会一直停在分区那一刻。\n"
      "read-index 用一次多数派确认，把「我还是不是 leader」这个前提重新验证一遍——这就是那 0.3 毫秒买的东西。",
      size=14, color=INK, line=1.5)
s.notes_slide.notes_text_frame.text = (
    "这是「哪段执行可以让客户端读到旧值」的正面回答：stale 分支。\n"
    "实验数据：孤主脏读返回 1000，新主上已经是 700；同一时刻的线性读在孤主上 3012 毫秒后拒答。\n"
    "强调：默认走线性读，脏读只在实验里打开当对照组。"
)
footer(s, 8, None)

# ============ 9 幂等 ============
s = slide_head("幂等：两层，缺一不可", "「重复扣款」是这类系统最容易犯的错")
two_col(s,
        "快路径（leader 内存）",
        ["在已应用的幂等表里查 req_id",
         "命中就直接返回上次结果，日志都不增长",
         "挡住绝大多数客户端重试",
         "缺点：leader 一换就没了 —— 所以它只是优化"],
        "慢路径（状态机内部）",
        ["状态机应用日志项时查同一张表",
         "命中就跳过执行、只回放结果",
         "这张表随日志一起复制，任何新主都认得",
         "这才是正确性的来源"],
        left_color=MUTED, right_color=GREEN)
txbox(s, Inches(0.85), Inches(6.05), Inches(11.6), Inches(0.6),
      "实测：同一 req_id 连发 3 次 → 生效 1 次、日志只增 1 条；杀掉 leader 后重试同一 req_id → 新主返回 duplicate，只扣一次。",
      size=13, color=BLUE, bold=True)
s.notes_slide.notes_text_frame.text = (
    "这页是我们在测试里撞出来的结论：一开始只做内存表，换主后重试就扣两次。\n"
    "被问「为什么不让客户端别重发」：客户端控制不了响应丢失——请求执行了、响应在路上丢了，"
    "客户端只能重发，它无法知道成败。所以幂等必须在服务端做。"
)
footer(s, 9, None)

# ============ 10 方法 ============
s = slide_head("实验怎么做才算数", "不做模拟，全部真跑")
bullets(s, [
    ("三个独立进程、真实 TCP、真实 fsync —— 不是模拟器，也不 mock 网络", 0),
    ("故障靠运行期注入：分区、10 秒延迟、消息重复 ×3、时钟倒退 60 秒、脏读开关", 0),
    ("六个实验各自起一套独立端口的集群，跑完销毁，互不干扰", 0),
    ("每组压测先热身 40 次，再测 200 次，取三轮中位数", 0),
    ("一条命令复现全部：python experiments/run_all.py（约 3 分钟）", 0),
    ("每个数字都落在 results/*.json，报告里的数据与之逐一对应", 0),
], size=17, gap=12)
s.notes_slide.notes_text_frame.text = (
    "强调可复现：老师如果问「这个数字怎么来的」，现场可以跑；离线也能看 results 里的 json。\n"
    "补一句方法学上的坑：最早测选主耗时是 1.6 秒，后来发现是对已死端口做 connect 卡了 500 毫秒，"
    "测量开销混进了被测的量。改成只轮询活着的进程才得到 390–1075 毫秒。"
)
footer(s, 10, None)

# ============ 11 关键数字 ============
s = slide_head("四个数字先给结论", "后面每一页都在解释它们")
metrics(s, [
    ("5000", "总余额恒为 5000", "所有实验的裁判：算错、重复扣、脑裂覆盖都会让它变"),
    ("4.1 ms", "单笔转账延迟", "其中 3.6 ms 是 fsync —— 多数派语义的价格"),
    ("582 ms", "选出新 leader", "范围 390–1075 ms；慢的那轮是落后节点白拉票"),
    ("374", "写吞吐 ops/s（并发4）", "并发1 为 254；瓶颈是 leader 的串行 fsync，不是网络"),
], top=Inches(1.85))
txbox(s, Inches(0.85), Inches(5.25), Inches(11.6), Inches(0.8),
      "这四个数字分别对应：正确性 · 单笔代价 · 故障恢复 · 吞吐上限。",
      size=14, color=MUTED)
s.notes_slide.notes_text_frame.text = (
    "先给结论，让老师知道我们有数。四个数字分别对应：正确性、单笔代价、故障恢复、吞吐上限。\n"
    "如果时间紧，这页可以只讲 5000 和 582。"
)
footer(s, 11, None)

# ============ 12 宕机 ============
s = slide_head("实验一：杀掉 leader 会怎样", "五轮实测，数据一次都没丢")
add_image(s, "fig_failover.png", top=Inches(1.62), height=Inches(3.9),
          caption="五轮 leader 宕机的选主耗时；橙色那一轮多花了一个选举超时")
txbox(s, Inches(0.85), Inches(5.85), Inches(11.6), Inches(1.0),
      "选主 390–1075 ms；重启节点 527–574 ms 追平日志；只杀一个 follower 时 15 笔写全部成功（平均 2.8 ms）。\n"
      "额外一组：落后 152 条时再宕机一次，重启后 850 ms 追平，三副本重新一致 —— 日志复制是幂等的，断点续传安全。",
      size=13, color=INK, line=1.5)
s.notes_slide.notes_text_frame.text = (
    "先讲正常面：四轮都在 390–527 毫秒，就是「选举超时 350–650 随机 + 一轮拉票」。\n"
    "再讲异常面（主动承认）：第一轮 1075 毫秒，因为落后的那个节点先超时，它的日志少一条，"
    "拉票被拒，只能等下一个超时。这是 Raft 的正常现象，也是我们没做 pre-vote 的代价。\n"
    "被问「挂一个和挂两个有什么区别」：挂一个多数派还在，照常写；挂两个就写不进去，是质变不是量变。"
)
footer(s, 12, None)

# ============ 13 脑裂 ============
s = slide_head("实验二：quorum 从 2 改成 1，失去什么", "两条都收到「成功」的写，恢复后少了一条")
add_image(s, "fig_split.png", top=Inches(1.6), height=Inches(3.5),
          caption="quorum=1 时两侧各自接受写入；恢复后任期低的一侧被整体覆盖")
txbox(s, Inches(0.85), Inches(5.5), Inches(11.6), Inches(1.3),
      "丢失的不是「性能」而是「正确性」：订单-001 消失，A 从 800 回到 1000，B 从 1200 回到 1000。\n"
      "顺带一个教训：转账不改变总额，所以「总余额守恒」查不出这种错 —— 不变式要挑对，我们额外写了一个标记 key。",
      size=13, color=INK, line=1.5)
s.notes_slide.notes_text_frame.text = (
    "这是全篇最有说服力的一组：把 quorum 改成 1，两边各自选出 leader、各自接受写，"
    "客户端两边都收到成功，恢复后一边被覆盖。\n"
    "银行场景里这等于凭空吞掉一笔已经通知客户的转账。\n"
    "注意那个细节：转账不动总额，所以总额守恒看不出问题，我们专门写了个「订单-001」标记 key 才暴露出来。"
)
footer(s, 13, None)

# ============ 14 幂等数据 ============
s = slide_head("实验三：重复请求只扣一次", "四组对照，含一次真实的响应丢失")
add_table(s,
          ["场景", "做法", "结果"],
          [["同一 req_id ×3", "连发三次转账 100", "生效 1 次，日志只增 1 条，A 1000→900"],
           ["对照组", "三个不同 req_id", "生效 3 次，扣了 300（客户端不做幂等的后果）"],
           ["响应丢失", "发完立刻断开连接", "服务端已扣 70；重试返回 duplicate，最终只扣 70"],
           ["换主后重试", "写成功后立刻杀掉 leader", "新主返回 duplicate，只扣一次 50"]],
          [2.5, 4.4, 5.6], top=Inches(1.95), size=13)
txbox(s, Inches(0.85), Inches(4.55), Inches(11.6), Inches(1.5),
      "第三行最像真实事故：请求执行了，响应在路上丢了，客户端只能重试。\n"
      "第四行是「幂等表必须放状态机」的证据 —— 放 leader 内存里，这个测试一定失败。",
      size=14, color=INK, line=1.5)
s.notes_slide.notes_text_frame.text = (
    "第三行是我们模拟「磁盘写成功但响应在途中丢失」的办法：报文发出去就关连接，永远读不到响应。\n"
    "第四行最关键：杀掉 leader 之后用同一个 req_id 打到新主，新主返回 duplicate，因为去重表在状态机里。"
)
footer(s, 14, None)

# ============ 15 故障模型 ============
s = slide_head("实验四：把题目列的故障一个个打上去", "每条都有现象、有数据")
add_table(s,
          ["故障", "现象", "数据结果"],
          [["消息延迟 10 s", "旧主失去多数派，客户端 498 ms 后收到 not_leader", "未提交日志被截断；重试只扣一次"],
           ["消息重复 ×3", "写入成功，日志只增 1 条", "同任期同下标的日志项被忽略"],
           ["时钟倒退 60 s", "写入照常成功", "任期不变、下标 5→6 单调，定序不依赖时钟"],
           ["分区后读旧值", "孤主脏读 1000，新主 700", "线性读 3012 ms 拒答；恢复 18 ms 追平"]],
          [2.4, 5.2, 4.9], top=Inches(1.95), size=13)
txbox(s, Inches(0.85), Inches(4.5), Inches(11.6), Inches(1.4),
      "延迟那一行的机制：心跳堵在路上 → follower 超时换主 → 新主用 noop 把旧主那条未提交的转账截断。\n"
      "客户端最终只扣一次，靠的是重试 + 幂等，而不是任何回滚机制。",
      size=13.5, color=INK, line=1.5)
s.notes_slide.notes_text_frame.text = (
    "四条依次讲，重点讲第一条和第四条。\n"
    "第一条说明「客户端不知道成败」是常态，所以必须幂等；第四条就是 read-index 的存在理由。\n"
    "时钟那条：我们从不拿时间戳做排序，所以拨回一分钟对正确性零影响。"
)
footer(s, 15, None)

# ============ 16 性能 ============
s = slide_head("实验五：这套设计的代价", "钱花在 fsync 上，天花板在单主上")
add_image(s, "fig_perf.png", top=Inches(1.58), height=Inches(3.6),
          caption="fsync 开关的吞吐对比：并发 1 时 253.8 对 1646.2 ops/s")
txbox(s, Inches(0.85), Inches(5.45), Inches(11.6), Inches(1.4),
      "① 落盘的代价是 6.5 倍吞吐（并发 1）；不 fsync 那一列，断电就丢已回「成功」的写，我们不换。\n"
      "② 并发 1→4 只涨 48%，瓶颈是 leader 的串行日志，加机器没用。\n"
      "③ 单 key 热点并不变慢（374 对 361）—— 但也说明：我们没法靠分片打散热点。",
      size=13, color=INK, line=1.5)
s.notes_slide.notes_text_frame.text = (
    "这一页要主动说「我们的上限在哪」，比被问出来好。\n"
    "三条：fsync 值这个钱；瓶颈在单主串行；单 key 热点不额外变慢，但也没手段打散。\n"
    "如果问「怎么提升」：批量提交（把多个写打包成一条日志项）或分片，我们都没做，前者是下一步。"
)
footer(s, 16, None)

# ============ 17 十个故障对照 ============
s = slide_head("题目列的十条，逐条对上", "这一页是备用页，被问再翻")
add_table(s,
          ["#", "问题", "我们的答案", "证据"],
          [["1", "副本突然宕机", "多数派在就继续服务；390–1075 ms 选新主", "实验一"],
           ["2", "分区 + 重复发送三次", "少数派拒写；同任期同下标日志项忽略", "实验二/四"],
           ["3", "延迟 10 s 后乱序到达", "心跳超时换主；旧任期报文被丢弃", "实验四"],
           ["4", "重启丢内存状态", "从 log.jsonl 回放到提交下标重建", "实验一"],
           ["5", "迁移一半时宕机", "落后 152 条时二次宕机，850 ms 追平", "实验一末"],
           ["6", "单 key 占 50% 请求", "不变慢，但无法打散", "实验五"],
           ["7", "两个客户端同时 CAS", "串行应用，一个成功一个版本冲突", "实验一"],
           ["8", "时间倒退一分钟", "只用（任期，下标）定序", "实验四"],
           ["9", "磁盘成功响应丢失", "同 req_id 重试，服务端 duplicate", "实验三"],
           ["10", "客户端重复发送", "幂等表在状态机，换主仍生效", "实验三"]],
          [0.7, 3.6, 6.3, 1.9], top=Inches(1.72), size=11.5, header_size=12)
s.notes_slide.notes_text_frame.text = (
    "备用页。如果老师问「题目列的故障你们都考虑了吗」，直接翻到这页逐条指。\n"
    "每条后面都有实验编号，能立刻翻回去看数据。"
)
footer(s, 17, None)

# ============ 18 坑 ============
s = slide_head("我们踩过的四个坑", "比「我们实现了 Raft」更能说明做过")
items = [
    ("客户端拿到了 noop 的结果",
     "换主时旧日志被截断，同一下标被新主的 noop 占用，等待队列按下标回填，把 noop 当成了转账结果。改成绑定日志项对象本身。"),
    ("写延迟被心跳拖住 100 ms",
     "原来只有心跳才触发复制。改成「有未复制日志就立刻发」，平均延迟从 100 ms 降到 4 ms。"),
    ("每 200 ms 的 meta 落盘卡住写路径",
     "持锁做 fsync，约 10% 的写莫名卡 60 ms。改成只 flush，p99 从 63 ms 降到 9 ms。"),
    ("压测数字一度是假的",
     "客户端每请求新建 TCP 连接，测出「关掉 fsync 反而更慢」。改成连接复用才看到真实的 6.5 倍。"),
]
y = Inches(1.8)
for i, (t, body) in enumerate(items):
    rect(s, Inches(0.85), y, Inches(11.6), Inches(1.15), fill=GRAY_L, line=None)
    txbox(s, Inches(1.1), y + Inches(0.13), Inches(3.6), Inches(0.9), t,
          size=14, bold=True, color=INK, line=1.2)
    txbox(s, Inches(4.9), y + Inches(0.15), Inches(7.3), Inches(0.9), body,
          size=11.5, color=MUTED, line=1.3)
    y += Inches(1.26)
s.notes_slide.notes_text_frame.text = (
    "第一个坑就是「版本比较代码删掉会怎样」的镜像：不比较版本，就会把别人的日志当成自己的结果。\n"
    "第四个坑是方法学教训：测出来的数不对，先怀疑测量方法。\n"
    "这一页的用意：让老师知道代码是我们自己调出来的，不是生成的。"
)
footer(s, 18, None)

# ============ 19 不足 ============
s = slide_head("不足与下一步", "我们知道自己的边界在哪")
two_col(s,
        "没做的（想清楚了才不做）",
        ["pre-vote：落后节点会白拉一轮票，代价是偶尔多花一个超时",
         "快照与日志压缩：几百条无所谓，上万条就要做",
         "成员变更：扩缩容要停机改配置",
         "分片：跨片转账要引入 2PC"],
        "如果重做，按这个顺序",
        ["① 批量提交：多个写打包成一条日志项，吞吐能上一个量级",
         "② pre-vote：消掉那一次 1075 ms",
         "③ 快照 + 日志压缩",
         "④ 最后才考虑分片（它会把 2PC 带回来）"],
        left_color=MUTED, right_color=BLUE)
s.notes_slide.notes_text_frame.text = (
    "主动交代边界，比被问出来好。\n"
    "注意强调「想清楚了才不做」，不是没做完：每一项都说得出为什么现在不做、什么时候该做。\n"
    "另外补一句：三个进程在一台机器上，验证的是协议正确性，不是故障域隔离；整机断电这类相关性故障测不出来。"
)
footer(s, 19, None)

# ============ 20 收尾 ============
s = prs.slides.add_slide(BLANK)
rect(s, Inches(0), Inches(0), Inches(0.22), H, fill=BLUE, shape=MSO_SHAPE.RECTANGLE)
txbox(s, Inches(1.1), Inches(1.5), Inches(10.6), Inches(1.2),
      "一句话总结", size=14, color=BLUE, bold=True)
txbox(s, Inches(1.1), Inches(2.0), Inches(10.8), Inches(2.0),
      "选单主，就不要多地区低延迟写；\n选 quorum=2，就不要「挂两个还能写」；\n"
      "选 fsync，就接受 6.5 倍的吞吐损失。",
      size=26, bold=True, line=1.5)
txbox(s, Inches(1.1), Inches(4.6), Inches(10.8), Inches(0.5),
      "这些不是缺陷清单，是设计的样子。", size=16, color=MUTED)
txbox(s, Inches(1.1), Inches(5.6), Inches(10.8), Inches(0.9),
      "代码仓库：https://github.com/<你的用户名>/distributed-kv-store\n"
      "演示：python src/run.py --fresh　→　http://127.0.0.1:8080",
      size=13, color=INK, line=1.6)
s.notes_slide.notes_text_frame.text = (
    "收尾停在这里，不要说「我们的系统还不完善」这种自我否定的话。\n"
    "改成：每个「是」都对应一个「不」，我们知道自己选了什么、放弃了什么。\n"
    "然后请老师提问，手上准备好：报告附录 C 有 10 个预演问题。"
)
footer(s, 20, None)

for i, sl in enumerate(prs.slides, start=1):
    if i > 1:
        pass

out = os.path.join(ROOT, "ppt", "分布式KV Store 讲解.pptx")
os.makedirs(os.path.dirname(out), exist_ok=True)
prs.save(out)
print("已生成：", out, "共", len(prs.slides.__iter__.__self__._sldIdLst), "页")
