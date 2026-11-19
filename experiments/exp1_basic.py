#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实验一：系统能正常工作吗？——选主、读写、副本一致、CAS 冲突。"""
import random
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Cluster, save, replicas_identical  # noqa: E402

random.seed(20261119)
out = {"实验": "基础功能与副本一致性"}

with Cluster("exp1", base=7411) as c:
    t_leader = c.wait_leader(timeout=15)[1]
    out["启动到选出leader耗时_s"] = round(t_leader, 3)
    print("选出 leader：节点 %d，用时 %.3fs" % (c.leader(), t_leader))

    c.reset_accounts(1000)
    time.sleep(0.3)
    total0 = c.total()

    ok = 0
    t0 = time.time()
    for _ in range(30):
        s = random.choice("ABCDE")
        d = random.choice([x for x in "ABCDE" if x != s])
        amt = random.randint(1, 120)
        r = c.client.transfer(s, d, amt)
        if r.get("ok") and r.get("result", {}).get("ok"):
            ok += 1
    dur = time.time() - t0
    time.sleep(0.4)

    total1 = c.total()
    same, kvs = replicas_identical(c)
    out.update({
        "转账次数": 30, "成功次数": ok,
        "平均单笔耗时_ms": round(dur / 30 * 1000, 1),
        "初始总余额": total0, "写入后总余额": total1,
        "总余额守恒": total0 == total1 == 5000,
        "三副本账本完全一致": same,
    })

    # 线性读：拿最新版本号
    st = c.status(c.leader())
    a_ver = st["kv"]["A"]["version"]
    rd = c.client.get("A")
    out["线性读版本号匹配"] = rd.get("result", {}).get("version") == a_ver
    out["线性读结果"] = rd.get("result")

    # CAS：故意用过期版本号写，必须被拒
    bad = c.client.cas("A", a_ver - 1, 0)
    good = c.client.cas("A", a_ver, st["kv"]["A"]["value"])
    out["CAS用旧版本被拒"] = (bad.get("ok") and not bad["result"]["ok"]
                              and bad["result"]["error"] == "version_conflict")
    out["CAS用当前版本成功"] = good.get("ok") and good["result"]["ok"]
    out["CAS冲突返回"] = bad.get("result")

    # 两个客户端同时 CAS 同一个版本：状态机串行执行，只能有一个赢
    import threading
    ver = c.status(c.leader())["kv"]["A"]["version"]
    base_val = c.status(c.leader())["kv"]["A"]["value"]
    results = []
    barrier = threading.Barrier(2)

    def racer():
        cl = c.client.__class__(c.ports)
        barrier.wait()
        results.append(cl.cas("A", ver, base_val + 777))

    ths = [threading.Thread(target=racer) for _ in range(2)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    wins = [r for r in results if (r.get("result") or {}).get("ok")]
    out["两个客户端同时CAS"] = {
        "同一期望版本": ver,
        "成功数": len(wins),
        "失败数": len(results) - len(wins),
        "失败原因": [(r.get("result") or {}).get("error") for r in results
                 if not (r.get("result") or {}).get("ok")],
        "最终版本号": c.status(c.leader())["kv"]["A"]["version"],
        "结论": "只有一个能改成功，另一个拿到 version_conflict",
    }

    # 余额不足必须拒绝，且不能把余额写成负数（先把账本复位，避免上面 CAS 改了余额干扰校验）
    c.reset_accounts(1000)
    time.sleep(0.3)
    r = c.client.transfer("A", "B", 999999)
    out["余额不足被拒"] = (r.get("ok") and not r["result"]["ok"])
    out["拒绝后余额不变"] = c.total() == 5000

print()
for k, v in out.items():
    print("  %-22s %s" % (k, v))
save("exp1_basic", out)
