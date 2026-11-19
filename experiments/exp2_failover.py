#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实验二：一个副本突然宕机，会发生什么？——选主耗时、服务可用性、重启追日志。"""
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Cluster, save, replicas_identical  # noqa: E402

out = {"实验": "副本宕机与故障切换"}
rounds = []

with Cluster("exp2", base=7421) as c:
    c.reset_accounts(1000)
    time.sleep(0.3)

    for r in range(5):
        ld = c.leader()
        old_term = c.status(ld)["term"]
        c.client.transfer("A", "B", 10)
        before_total = c.total()
        before_log = c.log_len(ld)

        t0 = time.time()
        c.kill(ld)
        new, _ = c.wait_leader(timeout=10, min_term=old_term + 1)
        dt = (time.time() - t0) * 1000

        # 新主上任后立刻写一笔，验证集群已经能服务
        wr = c.client.transfer("B", "C", 5)
        info = {"轮次": r + 1, "故障节点": ld, "旧任期": old_term,
                "新leader": new, "新任期": c.status(new)["term"],
                "选主耗时_ms": round(dt),
                "切换后写入成功": bool(wr.get("ok")),
                "切换前后总余额": [before_total, c.total()]}

        # 重启刚宕掉的节点，看它多久追上
        c.start_node(ld)
        t1 = time.time()
        catch = c.wait_caught_up(ld, timeout=20)
        info["重启追平日志耗时_ms"] = round((time.time() - t1) * 1000) if catch is not None else None
        info["重启后日志条数"] = c.log_len(ld)
        time.sleep(0.2)
        same, _ = replicas_identical(c)
        info["追平后三副本一致"] = same
        info["总余额"] = c.total()
        rounds.append(info)
        print("第%d轮：杀节点%d → 节点%d 当选，%.0fms；重启后 %.0fms 追平，数据一致=%s"
              % (r + 1, ld, new, dt, info["重启追平日志耗时_ms"] or -1, same))

    # 只杀一个从节点：多数派仍在，写入不该受影响
    ld = c.leader()
    follower = [i for i in range(1, 4) if i != ld][0]
    c.kill(follower)
    time.sleep(0.2)
    base_st = c.status(ld)
    lat = []
    ok = 0
    for i in range(15):
        t0 = time.time()
        r = c.client.transfer("C", "D", 1)
        lat.append((time.time() - t0) * 1000)
        ok += 1 if r.get("ok") else 0
    out.update({
        "轮次明细": rounds,
        "平均选主耗时_ms": round(statistics.mean([x["选主耗时_ms"] for x in rounds])),
        "选主耗时范围_ms": [min(x["选主耗时_ms"] for x in rounds),
                          max(x["选主耗时_ms"] for x in rounds)],
        "重启追平耗时明细_ms": [x["重启追平日志耗时_ms"] for x in rounds],
        "全部轮次数据守恒": all(x["切换前后总余额"] == [5000, 5000] for x in rounds),
        "只宕一个从节点": {
            "宕机节点": follower,
            "写入成功": ok, "写入总数": 15,
            "平均写延迟_ms": round(statistics.mean(lat), 1),
            "三副本尚存": sum(1 for s in c.all_status() if s.get("ok")),
            "总余额": c.total(),
        },
    })

    # 追赶日志追到一半再宕机一次：相当于"新节点迁移到一半宕机"
    c.heal()
    ld = c.leader()
    victim = [i for i in range(1, 4) if i != ld][0]
    c.kill(victim)
    for _ in range(120):
        c.client.transfer("A", "B", 1)
    behind = c.status(ld)["commit_index"] - (
        c.status(victim).get("commit_index", 0))
    c.start_node(victim)
    time.sleep(0.05)          # 刚开始复制就再杀一次
    c.kill(victim)
    c.start_node(victim)
    t2 = c.wait_caught_up(victim, timeout=25)
    time.sleep(0.3)
    same2, _ = replicas_identical(c)
    out["追赶途中再次宕机"] = {
        "落后条数": behind,
        "二次宕机后追平耗时_ms": round(t2 * 1000) if t2 is not None else None,
        "追平后三副本一致": same2,
        "总余额": c.total(),
        "结论": "日志复制是幂等的：重复的日志项按(任期,下标)比对后忽略，断点续传即可",
    }
    print("追赶途中再宕机：落后 %d 条，追平 %.0fms，一致=%s"
          % (behind, (t2 or 0) * 1000, same2))

print()
for k, v in out.items():
    if k != "轮次明细":
        print("  %-18s %s" % (k, v))
save("exp2_failover", out)
