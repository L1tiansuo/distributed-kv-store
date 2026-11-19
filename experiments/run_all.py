#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次跑完所有实验，汇总成一张表。报告里的数字全部来自这里。"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")

SCRIPTS = [
    ("exp1_basic.py", "基础功能与副本一致性"),
    ("exp2_failover.py", "副本宕机与故障切换"),
    ("exp3_quorum.py", "quorum 语义与脑裂"),
    ("exp4_idempotent.py", "幂等"),
    ("exp5_faults.py", "故障模型"),
    ("exp6_perf.py", "性能与代价"),
]


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for script, title in SCRIPTS:
        if only and only not in script:
            continue
        print("\n" + "=" * 70)
        print("▶ %s  %s" % (script, title))
        print("=" * 70)
        r = subprocess.run([sys.executable, os.path.join(HERE, script)], cwd=HERE)
        if r.returncode != 0:
            print("!! %s 失败，退出码 %d" % (script, r.returncode))

    print("\n" + "=" * 70)
    print("汇总")
    print("=" * 70)
    for f in sorted(os.listdir(RESULTS)):
        if not f.endswith(".json"):
            continue
        with open(os.path.join(RESULTS, f), encoding="utf-8") as fh:
            d = json.load(fh)
        print("\n[%s] %s" % (f, d.get("实验", "")))
        for k, v in d.items():
            if k in ("实验", "轮次明细", "用例"):
                continue
            s = json.dumps(v, ensure_ascii=False)
            print("  · %s: %s" % (k, s if len(s) < 160 else s[:160] + "..."))


if __name__ == "__main__":
    main()
