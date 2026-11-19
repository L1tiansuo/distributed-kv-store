#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验四：重复请求会不会重复扣钱？——幂等。
  A. 同一个 req_id 连发 3 次
  B. 对照组：3 个不同 req_id（等于客户端没做幂等）
  C. 响应丢失：客户端 20ms 就放弃，服务端其实已提交，然后用同一 req_id 重试
  D. 主节点在途中被杀，客户端找新主重试同一 req_id
"""
import os
import sys
import json
import socket
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Cluster, save  # noqa: E402

out = {"实验": "幂等"}


def bal(c, key):
    r = c.client.get(key)
    return (r.get("result") or {}).get("value")


with Cluster("exp4", base=7451) as c:
    c.reset_accounts(1000)
    time.sleep(0.3)

    # ---- A：同一 req_id 连发 3 次 ----
    rid = c.client.new_req_id()
    log0, a0 = c.log_len(c.leader()), bal(c, "A")
    rs = [c.client.transfer("A", "B", 100, req_id=rid) for _ in range(3)]
    time.sleep(0.2)
    log1, a1 = c.log_len(c.leader()), bal(c, "A")
    applied = sum(1 for r in rs if (r.get("result") or {}).get("ok")
                  and not (r.get("result") or {}).get("duplicate"))
    out["A_同一req_id连发3次"] = {
        "请求次数": 3, "真正生效次数": applied,
        "日志增长条数": log1 - log0,
        "A余额": [a0, a1], "扣款金额": a0 - a1,
        "后两次是否标记duplicate": [(r.get("result") or {}).get("duplicate", False) for r in rs],
        "总余额": c.total(),
    }
    print("A：连发 3 次 → 生效 %d 次，A 从 %s 变 %s，日志只增 %d 条"
          % (applied, a0, a1, log1 - log0))

    # ---- B：对照组，3 个不同 req_id ----
    c.reset_accounts(1000)
    time.sleep(0.3)
    b0 = bal(c, "A")
    for _ in range(3):
        c.client.transfer("A", "B", 100)
    b1 = bal(c, "A")
    out["B_不用req_id（对照组）"] = {"A余额": [b0, b1], "扣款金额": b0 - b1, "总余额": c.total()}
    print("B：3 个不同 req_id → A 从 %s 变 %s（扣了 %s）" % (b0, b1, b0 - b1))

    # ---- C：响应丢失（发出去就断开连接，永远读不到响应）----
    c.reset_accounts(1000)
    time.sleep(0.3)
    rid = c.client.new_req_id()
    c0 = bal(c, "C")
    msg = {"type": "client", "op": "transfer", "from": "C", "to": "D",
           "amount": 70, "req_id": rid}
    ld = c.leader()
    s = socket.create_connection(("127.0.0.1", c.ports[ld - 1]), timeout=2)
    s.sendall((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
    s.close()                                        # 不等响应，连接直接断掉
    time.sleep(1.0)
    c_mid = bal(c, "C")                              # 服务端其实已经扣了
    r2 = c.client.transfer("C", "D", 70, req_id=rid)  # 客户端拿同一 req_id 重试
    time.sleep(0.2)
    c1 = bal(c, "C")
    out["C_响应丢失后重试"] = {
        "第一次客户端看到": "连接断开，不知道成败",
        "第一次后余额（服务端已扣）": [c0, c_mid],
        "重试结果是否duplicate": (r2.get("result") or {}).get("duplicate"),
        "最终余额": c1, "总扣款": c0 - c1, "总余额": c.total(),
    }
    print("C：响应丢失后服务端已扣 %s，重试 duplicate=%s，最终共扣 %s"
          % (c0 - c_mid, (r2.get("result") or {}).get("duplicate"), c0 - c1))

    # ---- D：写成功但主节点随即被杀，换主重试 ----
    c.reset_accounts(1000)
    time.sleep(0.3)
    rid = c.client.new_req_id()
    d0 = bal(c, "D")
    r_ok = c.client.transfer("D", "E", 50, req_id=rid)
    time.sleep(0.35)          # 让从节点也把这条日志应用掉
    ld = c.leader()
    term = c.status(ld)["term"]
    c.kill(ld)
    new, _ = c.wait_leader(timeout=10, min_term=term + 1)
    c.wait_caught_up(new, timeout=10)
    d_mid = bal(c, "D")
    r_dup = c.client.transfer("D", "E", 50, req_id=rid)   # 同一 req_id 打到新主
    time.sleep(0.2)
    d1 = bal(c, "D")
    out["D_主切换后重试"] = {
        "原写入成功": bool(r_ok.get("ok")), "被杀leader": ld, "新leader": new,
        "切换后duplicate": (r_dup.get("result") or {}).get("duplicate"),
        "D余额变化": [d0, d_mid, d1], "是否只扣一次": (d0 - d1) == 50,
        "总余额": c.total(),
    }
    print("D：主切换后重试同一 req_id → duplicate=%s，D 共扣 %s"
          % ((r_dup.get("result") or {}).get("duplicate"), d0 - d1))

print()
for k, v in out.items():
    if k != "实验":
        print("  %-18s %s" % (k, v))
save("exp4_idempotent", out)
