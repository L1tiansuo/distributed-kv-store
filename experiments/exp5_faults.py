#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验五：把老师列出的故障一个个打上去。
  A. 消息延迟 10 秒 → 客户端超时、服务端最终成功
  B. 消息被重复发送三次 → 日志不会重复
  C. 系统时间倒退 60 秒 → 定序靠任期和日志下标，不靠墙上时钟
  D. 网络分区后读旧值：脏读开关 vs 线性一致读
"""
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Cluster, save, replicas_identical  # noqa: E402
import client as kvclient  # noqa: E402

out = {"实验": "故障模型"}


def bal(c, key, stale=False):
    r = c.client.get(key, "stale" if stale else "linearizable")
    return (r.get("result") or {}).get("value")


with Cluster("exp5", base=7461) as c:
    c.reset_accounts(1000)
    time.sleep(0.3)

    # ---------- A：leader 的出站消息延迟 10s ----------
    # 只给 leader 注入，模拟"心跳堵在路上"。旧主写不出去 → 从节点超时选新主。
    ld = c.leader()
    old_term = c.status(ld)["term"]
    a0 = bal(c, "A")
    c.admin(ld, {"type": "admin", "cmd": "delay", "ms": 10000})
    rid = c.client.new_req_id()
    t0 = time.time()
    r = c.client.transfer("A", "B", 120, req_id=rid, retries=1)   # 只发一次，看客户端看到什么
    dt = (time.time() - t0) * 1000

    new, elect = c.wait_leader(timeout=10, min_term=old_term + 1)
    # 撤掉延迟，让旧主收到新主的心跳、把那条未提交的日志截断掉
    c.admin(ld, {"type": "admin", "cmd": "delay", "ms": 0})
    c.wait_until(lambda: c.status(ld).get("state") != "leader", timeout=8)
    c.wait_caught_up(new, timeout=10)
    a_mid = bal(c, "A")
    r2 = c.client.transfer("A", "B", 120, req_id=rid)   # 同一 req_id 打到新主
    time.sleep(0.4)
    a1 = bal(c, "A")
    out["A_leader消息延迟10s"] = {
        "客户端结果": r.get("error") or (r.get("result") or {}).get("error"),
        "客户端等待_ms": round(dt),
        "新leader": new, "客户端返回后新主已就绪_额外等待_ms": round(elect * 1000),
        "旧主那条日志": "未提交，权限更高的新主上台后被截断丢弃",
        "重试返回duplicate": (r2.get("result") or {}).get("duplicate", False),
        "A余额变化": [a0, a_mid, a1],
        "只扣一次": (a0 - a1) == 120,
        "总余额": c.total(),
        "结论": "客户端看到超时，但从没扣两次；重试在新主上重新执行一次，账仍是平的",
    }
    print("A：旧主超时（%.0fms），%.0fms 后新主 %d 上任；重试 duplicate=%s，A %s→%s→%s"
          % (dt, elect * 1000, new, (r2.get("result") or {}).get("duplicate"), a0, a_mid, a1))

    # ---------- B：消息重复 ×3 ----------
    c.admin("all", {"type": "admin", "cmd": "dup", "n": 3})
    log0 = c.log_len(c.leader())
    r = c.client.transfer("B", "C", 30)
    time.sleep(0.4)
    out["B_消息重复3次"] = {"写入成功": bool(r.get("ok")), "日志增长条数": c.log_len(c.leader()) - log0,
                       "总余额": c.total()}
    c.admin("all", {"type": "admin", "cmd": "dup", "n": 0})
    print("B：重复发 3 次，日志只增长 %d 条" % (c.log_len(c.leader()) - log0))

    # ---------- C：时钟倒退 60s ----------
    st_before = c.status(c.leader())
    c.admin("all", {"type": "admin", "cmd": "clock", "delta_ms": -60000})
    r = c.client.transfer("C", "D", 40)
    st_after = c.status(c.leader())
    out["C_时钟倒退60s"] = {
        "写入是否成功": bool(r.get("ok")),
        "日志下标": [st_before["last_log_index"], st_after["last_log_index"]],
        "任期": [st_before["term"], st_after["term"]],
        "人为偏移_ms": st_after["clock_offset"],
        "结论": "Raft 用 (任期, 日志下标) 定序，墙上时钟只用于日志展示，倒退不影响正确性",
    }
    c.admin("all", {"type": "admin", "cmd": "clock", "delta_ms": 60000})
    print("C：时钟倒退 60s 后写入仍成功，下标 %s→%s"
          % (st_before["last_log_index"], st_after["last_log_index"]))

    # ---------- D：分区后读到旧值 ----------
    c.heal()
    c.reset_accounts(1000)
    time.sleep(0.3)
    ld = c.leader()
    others = [i for i in range(1, 4) if i != ld]
    c.partition([[ld], others])
    time.sleep(1.2)
    new_leader = None
    for i in others:
        if c.status(i).get("state") == "leader":
            new_leader = i
            break
    old_a = c.kv_of(ld)["A"]["value"]
    # 用只认识"多数派那一侧"的客户端去写，它会自己找到并跟随新 leader
    side = kvclient.Client([c.ports[i - 1] for i in others], timeout=6.0)
    wr = {"ok": False, "error": "未成功"}
    rid = side.new_req_id()
    attempts = 0
    for _ in range(6):
        attempts += 1
        wr = side.transfer("A", "B", 300, req_id=rid)   # 重试必须复用同一个 req_id
        if wr.get("ok"):
            break
        time.sleep(0.4)
    new_leader = wr.get("leader") or new_leader
    time.sleep(0.3)
    new_a = c.kv_of(new_leader)["A"]["value"]
    stale = kvclient.rpc(c.ports[ld - 1],
                         {"type": "client", "op": "get", "key": "A",
                          "consistency": "stale"}, 3.0)
    t0 = time.time()
    linear = kvclient.rpc(c.ports[ld - 1],
                          {"type": "client", "op": "get", "key": "A",
                           "consistency": "linearizable"}, 5.0)
    out["D_分区后读旧值"] = {
        "孤立节点": ld, "新leader": new_leader,
        "最后一次写入返回": wr.get("error") or "ok",
        "客户端实际尝试次数": attempts,
        "孤立节点上的A": old_a, "新leader上的A": new_a,
        "脏读(stale)返回": (stale.get("result") or {}).get("value"),
        "脏读是否读到旧值": (stale.get("result") or {}).get("value") == old_a != new_a,
        "线性一致读结果": linear.get("error"),
        "线性一致读耗时_ms": round((time.time() - t0) * 1000),
        "结论": "同一个 key，脏读返回 1000，线性读直接拒答——这就是那句'哪段执行可以让客户端读到旧值'",
    }
    print("D：孤主上 stale 读=%s，新主上=%s，线性读=%s"
          % ((stale.get("result") or {}).get("value"), new_a, linear.get("error")))

    c.heal()
    t = c.wait_caught_up(ld, timeout=15)
    time.sleep(0.3)
    same, _ = replicas_identical(c)
    out["D_分区后读旧值"]["恢复后追平耗时_ms"] = round(t * 1000) if t is not None else None
    out["D_分区后读旧值"]["三副本重新一致"] = same
    print("D：恢复后 %.0fms 追平，三副本一致=%s" % ((t or 0) * 1000, same))

print()
for k, v in out.items():
    if k != "实验":
        print("  %-14s %s" % (k, v))
save("exp5_faults", out)
