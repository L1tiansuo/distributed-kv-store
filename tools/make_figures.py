#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成报告和 PPT 用的图。数据全部取自 results/ 里的实验结果。"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "docs", "figures")
os.makedirs(OUT, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

INK = "#1c2233"
MUTED = "#68708a"
BLUE = "#2f6bff"
BLUE_L = "#eaf0ff"
GREEN = "#12a05c"
GREEN_L = "#e7f7ee"
GRAY_L = "#f2f4fa"
LINE = "#c9d0e2"


def box(ax, x, y, w, h, title, sub="", fc="#ffffff", ec=LINE, tsize=11):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                linewidth=1.2, edgecolor=ec, facecolor=fc, zorder=2))
    ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center",
            fontsize=tsize, color=INK, weight="bold", zorder=3)
    if sub:
        ax.text(x + w / 2, y + h * 0.3, sub, ha="center", va="center",
                fontsize=8.5, color=MUTED, zorder=3, linespacing=1.5)


def arrow(ax, p1, p2, text="", color=BLUE, style="-|>", rad=0.0, dx=0, dy=0.012, fs=8):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=12,
                                 linewidth=1.3, color=color, zorder=1,
                                 connectionstyle="arc3,rad=%s" % rad))
    if text:
        ax.text((p1[0] + p2[0]) / 2 + dx, (p1[1] + p2[1]) / 2 + dy, text,
                ha="center", va="bottom", fontsize=fs, color=color, zorder=4)


def fig_arch():
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    box(ax, 0.30, 0.84, 0.40, 0.12, "客户端 client.py",
        "req_id 幂等 · 缓存 leader · 失败跟随重定向", fc=GRAY_L, tsize=11)
    box(ax, 0.735, 0.735, 0.245, 0.10, "网页控制台 console.html",
        "杀节点 / 分区 / 延迟 / 压测", fc=GRAY_L, tsize=9.5)

    box(ax, 0.04, 0.30, 0.25, 0.38, "节点 1  ·  leader",
        "追加日志 → 复制 → 多数派提交\n状态机：账户 + 版本号 + 幂等表\nWAL: log.jsonl (fsync)",
        fc=BLUE_L, ec="#b9cafa")
    box(ax, 0.375, 0.30, 0.25, 0.38, "节点 2  ·  follower",
        "接收 AppendEntries\n按 (任期, 下标) 校验并落盘\n崩溃后从日志重放",
        fc="#ffffff")
    box(ax, 0.71, 0.30, 0.25, 0.38, "节点 3  ·  follower",
        "与节点 2 相同\n投票 + 日志复制", fc="#ffffff")

    box(ax, 0.06, 0.06, 0.88, 0.14, "一致性：写 = 多数派(2/3) 落盘才回成功　读 = read-index 确认仍是 leader",
        "分区时少数派拒写（返回 not_leader），绝不两边各写各的", fc=GREEN_L, ec="#bfe8d3", tsize=10)

    arrow(ax, (0.44, 0.84), (0.16, 0.688), "① 转账请求", dx=-0.03, dy=0.01)
    arrow(ax, (0.24, 0.688), (0.56, 0.842), "⑥ 结果", color=GREEN, dx=0.045, dy=-0.055)
    arrow(ax, (0.29, 0.52), (0.375, 0.52), "② 复制", dx=0, dy=0.018)
    arrow(ax, (0.625, 0.52), (0.71, 0.52), "② 复制", dx=0, dy=0.018)
    arrow(ax, (0.375, 0.44), (0.29, 0.44), "③ 确认", color=GREEN, dx=0, dy=-0.042)
    arrow(ax, (0.71, 0.44), (0.625, 0.44), "③ 确认", color=GREEN, dx=0, dy=-0.042)
    ax.text(0.5, 0.245, "④ 拿到 2 个节点确认 → 提交　⑤ 状态机按顺序应用（一笔转账同时改两个账户）",
            ha="center", va="center", fontsize=9, color=MUTED)

    fig.savefig(os.path.join(OUT, "fig_arch.png"), dpi=200, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)


def fig_failover():
    d = json.load(open(os.path.join(ROOT, "results", "exp2_failover.json"), encoding="utf-8"))
    rows = d["轮次明细"]
    labels = ["第%d轮\n杀节点%d" % (r["轮次"], r["故障节点"]) for r in rows]
    vals = [r["选主耗时_ms"] for r in rows]
    colors = [BLUE if v < 800 else "#f0a020" for v in vals]

    fig, ax = plt.subplots(figsize=(7.6, 3.4))
    bars = ax.bar(labels, vals, color=colors, width=0.55)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 18, "%d ms" % v, ha="center",
                fontsize=10, color=INK)
    ax.axhline(650, ls="--", lw=1, color=MUTED)
    ax.text(4.42, 672, "选举超时上限 650ms", fontsize=8.5, color=MUTED, ha="right")
    ax.set_ylim(0, max(vals) * 1.25)
    ax.set_ylabel("选出新 leader 耗时 (ms)", color=MUTED)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.set_title("")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_failover.png"), dpi=200, facecolor="white")
    plt.close(fig)


def fig_perf():
    d = json.load(open(os.path.join(ROOT, "results", "exp6_perf.json"), encoding="utf-8"))
    c = d["用例"]
    groups = ["并发 1", "并发 4", "并发 4\n单 key 热点"]
    sync = [c["fsync开_并发1_multi"]["吞吐_ops_per_s"], c["fsync开_并发4_multi"]["吞吐_ops_per_s"],
            c["fsync开_并发4_single"]["吞吐_ops_per_s"]]
    nosync = [c["fsync关_并发1_multi"]["吞吐_ops_per_s"], c["fsync关_并发4_multi"]["吞吐_ops_per_s"],
              c["fsync关_并发4_single"]["吞吐_ops_per_s"]]

    x = range(len(groups))
    fig, ax = plt.subplots(figsize=(7.6, 3.4))
    w = 0.36
    b1 = ax.bar([i - w / 2 for i in x], sync, w, label="fsync 开（默认）", color=BLUE)
    b2 = ax.bar([i + w / 2 for i in x], nosync, w, label="fsync 关（仅对照）", color="#c9d0e2")
    for bs in (b1, b2):
        for b in bs:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 60,
                    "%.0f" % b.get_height(), ha="center", fontsize=9, color=INK)
    ax.set_xticks(list(x)); ax.set_xticklabels(groups)
    ax.set_ylabel("吞吐 (ops/s)", color=MUTED)
    ax.set_ylim(0, max(nosync) * 1.18)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.set_title("")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_perf.png"), dpi=200, facecolor="white")
    plt.close(fig)


def fig_split():
    """quorum=1 脑裂示意（用实验三的真实数据）。"""
    d = json.load(open(os.path.join(ROOT, "results", "exp3_quorum.json"), encoding="utf-8"))
    b = d["B_quorum等于1"]
    fig, ax = plt.subplots(figsize=(8.4, 3.6))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    box(ax, 0.04, 0.52, 0.40, 0.36, "分区 A 侧：节点 3（自认 leader）",
        "A→B 转 200 成功\n写入 订单-001 成功\n账面 A=800 B=1200", fc=BLUE_L, ec="#b9cafa", tsize=9.5)
    box(ax, 0.56, 0.52, 0.40, 0.36, "分区 B 侧：节点 1、2",
        "D→E 转 300 成功\n账面 D=700 E=1300", fc="#fff5e8", ec="#f2ddb4", tsize=9.5)
    ax.plot([0.5, 0.5], [0.42, 0.9], ls="--", lw=1.3, color="#e0483d")
    ax.text(0.5, 0.35, "网络分区", ha="center", fontsize=9, color="#e0483d")
    ax.text(0.5, 0.16, "恢复后：任期低的一侧被覆盖 → 订单-001 消失，A 回到 1000，B 回到 1000\n"
                       "两笔写客户端都收到了「成功」",
            ha="center", fontsize=9.5, color=INK,
            bbox=dict(boxstyle="round,pad=0.45", fc=GREEN_L, ec="#bfe8d3"))
    fig.savefig(os.path.join(OUT, "fig_split.png"), dpi=200, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    fig_arch()
    fig_failover()
    fig_perf()
    fig_split()
    print("图已生成：", os.listdir(OUT))
