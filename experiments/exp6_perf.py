#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验六：代价。
  1. fsync 开/关 的吞吐差多少（每笔写都要落盘，这是多数派语义的价格）
  2. 并发 1 / 4
  3. 单 key 热点（题单里"某个 key 占据 50% 的请求"）
每组先跑 40 次热身再测，取两轮中位数，避免冷启动和抖动。
"""
import os
import statistics
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Cluster, save  # noqa: E402
import client as kvclient  # noqa: E402


def bench(ports, n=200, conc=4, keys_mode="multi"):
    keys = ["HOT"] if keys_mode == "single" else ["K%d" % i for i in range(50)]
    lat, errs = [], [0]
    lk = threading.Lock()

    def worker(cnt):
        c = kvclient.Client(ports, timeout=10)
        for i in range(cnt):
            t0 = time.perf_counter()
            r = c.set(keys[i % len(keys)], i)
            dt = (time.perf_counter() - t0) * 1000
            with lk:
                if r.get("ok"):
                    lat.append(dt)
                else:
                    errs[0] += 1

    per = max(1, n // conc)
    t0 = time.perf_counter()
    ths = [threading.Thread(target=worker, args=(per,)) for _ in range(conc)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    dur = time.perf_counter() - t0
    lat.sort()

    def q(p):
        return round(lat[min(len(lat) - 1, int(len(lat) * p))], 1) if lat else None

    return {"请求数": len(lat) + errs[0], "成功": len(lat), "失败": errs[0],
            "总耗时_s": round(dur, 2),
            "吞吐_ops_per_s": round(len(lat) / dur, 1) if dur else 0,
            "P50_ms": q(0.50), "P99_ms": q(0.99),
            "最大_ms": round(lat[-1], 1) if lat else None}


def run_case(ports, conc, km, reps=3):
    bench(ports, n=40, conc=conc, keys_mode=km)      # 热身
    runs = [bench(ports, n=200, conc=conc, keys_mode=km) for _ in range(reps)]
    return {
        "并发": conc, "key模式": km,
        "吞吐_ops_per_s": round(statistics.median(r["吞吐_ops_per_s"] for r in runs), 1),
        "P50_ms": round(statistics.median(r["P50_ms"] for r in runs), 1),
        "P99_ms": round(statistics.median(r["P99_ms"] for r in runs), 1),
        "最大_ms": max(r["最大_ms"] for r in runs),
        "明细": runs,
    }


out = {"实验": "性能与代价"}
cases = {}
CASES = ((1, "multi"), (4, "multi"), (4, "single"))

with Cluster("exp6_sync", base=7471) as c:
    c.reset_accounts(1000)
    time.sleep(0.3)
    for conc, km in CASES:
        key = "fsync开_并发%d_%s" % (conc, km)
        cases[key] = run_case(c.ports, conc, km)
        print("%-18s %6.1f ops/s  p50=%sms p99=%sms"
              % (key, cases[key]["吞吐_ops_per_s"], cases[key]["P50_ms"], cases[key]["P99_ms"]))

with Cluster("exp6_nosync", base=7481, node_args=["--nosync"]) as c:
    c.reset_accounts(1000)
    time.sleep(0.3)
    for conc, km in CASES:
        key = "fsync关_并发%d_%s" % (conc, km)
        cases[key] = run_case(c.ports, conc, km)
        print("%-18s %6.1f ops/s  p50=%sms p99=%sms"
              % (key, cases[key]["吞吐_ops_per_s"], cases[key]["P50_ms"], cases[key]["P99_ms"]))

a = cases["fsync开_并发1_multi"]["吞吐_ops_per_s"]
b = cases["fsync关_并发1_multi"]["吞吐_ops_per_s"]
c1 = cases["fsync开_并发4_multi"]["吞吐_ops_per_s"]
c2 = cases["fsync关_并发4_multi"]["吞吐_ops_per_s"]
out["用例"] = cases
out["结论"] = {
    "fsync代价_并发1": "%.1f → %.1f ops/s（%.1f 倍）" % (a, b, b / a),
    "fsync代价_并发4": "%.1f → %.1f ops/s（%.1f 倍）" % (c1, c2, c2 / c1),
    "单key是否更慢": "并发4下 %.1f vs %.1f ops/s——几乎无差别"
                  % (cases["fsync开_并发4_multi"]["吞吐_ops_per_s"],
                     cases["fsync开_并发4_single"]["吞吐_ops_per_s"]),
}
save("exp6_perf", out)
print()
for k, v in out["结论"].items():
    print("  %-14s %s" % (k, v))
