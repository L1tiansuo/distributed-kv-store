#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 v3 PPT 新增的三张示意图。

1. fig_log.png      日志复制与未复制尾部
2. fig_idem.png     同一请求连发三次的余额曲线
3. fig_latency.png  单笔写延迟分解与并发下的排队

数据来自 results/exp4_idempotent.json、results/exp6_perf.json 与本机实测。
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "docs", "figures")

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

NAVY = "#1F3A5F"
INK = "#1C2233"
MUTED = "#68708A"
ACCENT = "#D97706"
LINE = "#C9D0E2"

T1 = "#E9EEF5"
T2 = "#C3D2EA"
T3 = "#F3C98B"


def fig_log():
    """三条日志并排，第三台尾部缺一格。"""
    fig, ax = plt.subplots(figsize=(11, 4.3), dpi=200)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    terms = [1, 1, 2, 2, 2, 2, 2]
    rows = [
        ("节点 1", "leader · term 2", terms, 7),
        ("节点 2", "follower", terms, 7),
        ("节点 3", "follower", terms, 6),
    ]
    x0, colw, rowh = 0.19, 0.098, 0.17
    ys = [0.72, 0.48, 0.24]

    # 列号
    for i in range(7):
        ax.text(x0 + i * colw + colw / 2, 0.92, str(i + 1), ha="center", va="center",
                fontsize=10, color=MUTED)
    ax.text(x0 + 7 * colw / 2, 0.985, "日志下标 index", ha="center", va="center",
            fontsize=10.5, color=MUTED)

    for (name, role, ts, n), y in zip(rows, ys):
        ax.text(0.155, y + rowh * 0.62, name, ha="right", va="center",
                fontsize=12, color=INK, weight="bold")
        ax.text(0.155, y + rowh * 0.2, role, ha="right", va="center",
                fontsize=9, color=MUTED)
        for i in range(7):
            x = x0 + i * colw
            if i < n:
                t = ts[i]
                fc = T1 if t == 1 else (T2 if t == 2 else T3)
                ax.add_patch(Rectangle((x, y), colw * 0.88, rowh, facecolor=fc,
                                       edgecolor=LINE, linewidth=1.0, zorder=2))
                ax.text(x + colw * 0.44, y + rowh * 0.62, "term %d" % t,
                        ha="center", va="center", fontsize=8.5, color=INK, zorder=3)
                ax.text(x + colw * 0.44, y + rowh * 0.22, "命令",
                        ha="center", va="center", fontsize=8, color=MUTED, zorder=3)
            else:
                ax.add_patch(Rectangle((x, y), colw * 0.88, rowh, facecolor="white",
                                       edgecolor=ACCENT, linewidth=1.4,
                                       linestyle=(0, (4, 3)), zorder=2))
                ax.text(x + colw * 0.44, y + rowh * 0.5, "空",
                        ha="center", va="center", fontsize=9, color=ACCENT, zorder=3)

    # 右注：未复制部分
    ax.annotate("", xy=(x0 + 6 * colw + 0.002, 0.24 + rowh * 0.5),
                xytext=(x0 + 5 * colw + 0.88 * colw - 0.002, 0.24 + rowh * 0.5),
                arrowprops=dict(arrowstyle="-|>", color=ACCENT, lw=1.8))
    ax.text(x0 + 7 * colw, 0.115, "节点 3 还差这一条\nnext_index[3] = 7",
            ha="right", va="top", fontsize=9.5, color=ACCENT, linespacing=1.5)

    # 左注：日志项的结构
    ax.text(0.02, 0.04, "每条日志项 =（下标, 任期, 命令）",
            ha="left", va="center", fontsize=9.5, color=MUTED)

    fig.subplots_adjust(left=0.02, right=0.99, top=0.99, bottom=0.02)
    fig.savefig(os.path.join(OUT, "fig_log.png"), facecolor="white")
    plt.close(fig)


def fig_idem():
    """三次同一 req_id 请求后的余额。"""
    fig, ax = plt.subplots(figsize=(8.6, 4.2), dpi=200)

    labels = ["第 1 次", "第 2 次", "第 3 次"]
    vals = [900, 800, 800]
    colors = [NAVY, "#C9D0E2", "#C9D0E2"]
    bars = ax.bar(labels, vals, width=0.5, color=colors, edgecolor="white")

    ax.set_ylim(600, 1000)
    ax.set_ylabel("账户 A 余额（元）", fontsize=11, color=INK)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(LINE)
    ax.spines["bottom"].set_color(LINE)
    ax.tick_params(colors=MUTED, labelsize=10.5)

    for b, v, i in zip(bars, vals, range(3)):
        ax.text(b.get_x() + b.get_width() / 2, v + 12, str(v), ha="center",
                fontsize=13, color=INK, weight="bold")
        tag = "index 4\n真正生效" if i == 0 else "index 4\nduplicate"
        ax.text(b.get_x() + b.get_width() / 2, 640, tag, ha="center",
                fontsize=9.5, color=("white" if i == 0 else MUTED), linespacing=1.6)

    ax.annotate("", xy=(1.25, 800), xytext=(0.75, 800),
                arrowprops=dict(arrowstyle="-", color=LINE, lw=1, linestyle=":"))
    ax.text(1.5, 915, "总额始终 5000", ha="center", fontsize=10, color=MUTED)

    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_idem.png"), facecolor="white")
    plt.close(fig)


def fig_latency():
    """单笔写 4.1ms 的构成，以及并发下的排队。"""
    fig, ax = plt.subplots(figsize=(10.5, 3.4), dpi=200)

    rows = [
        ("并发 1 · 单笔", 3.6, 0.5, 4.1),
        ("并发 4 · 中位", 3.6, 6.7, 10.3),
    ]
    for i, (label, fsync, other, total) in enumerate(rows):
        y = 0.66 - i * 0.34
        ax.barh(y, fsync, height=0.17, color=NAVY, edgecolor="white")
        ax.barh(y, other, left=fsync, height=0.17, color="#DCE3F0", edgecolor="white")
        ax.text(-0.2, y, label, ha="right", va="center", fontsize=11, color=INK)
        ax.text(fsync / 2, y, "fsync 3.6 ms", ha="center", va="center",
                fontsize=10, color="white", weight="bold")
        if other > 3:
            ax.text(fsync + other / 2, y, "排队 %.1f ms" % other, ha="center",
                    va="center", fontsize=10, color=INK)
        ax.text(total + 0.22, y, "%.1f ms" % total, ha="left", va="center",
                fontsize=12, color=ACCENT, weight="bold")

    ax.text(4.1, 0.86, "其余 0.5 ms：网络与处理", ha="left", va="center",
            fontsize=9.5, color=MUTED)

    ax.set_xlim(0, 12.4)
    ax.set_ylim(0.12, 0.92)
    ax.set_yticks([])
    ax.set_xlabel("单笔写从发出到收到应答（毫秒）", fontsize=10.5, color=INK)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.tick_params(colors=MUTED, labelsize=10)

    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_latency.png"), facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    fig_log()
    fig_idem()
    fig_latency()
    for n in ("fig_log.png", "fig_idem.png", "fig_latency.png"):
        print("已生成", os.path.join(OUT, n))
