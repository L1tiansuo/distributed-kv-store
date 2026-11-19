#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验三：quorum 到底意味着什么？
  A. 3 节点里挂掉 2 个 → 写不进去（拿不到多数派）
  B. quorum 从 2 改成 1 → 网络分区时两边各写各的，恢复后一方数据直接消失
"""
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Cluster, save  # noqa: E402
import client as kvclient  # noqa: E402

out = {"实验": "quorum 语义与脑裂"}

# ---------- A：失去多数派 ----------
with Cluster("exp3a", base=7431) as c:
    c.reset_accounts(1000)
    time.sleep(0.3)
    ld = c.leader()
    followers = [i for i in range(1, 4) if i != ld]
    print("leader=%d，准备杀掉 %s" % (ld, followers))

    c.kill(followers[0])
    c.kill(followers[1])
    time.sleep(0.3)
    st = c.status(ld)
    before_commit = st["commit_index"]

    t0 = time.time()
    r = c.client.transfer("A", "B", 100, retries=1)
    dt = (time.time() - t0) * 1000
    time.sleep(0.4)
    st2 = c.status(ld)

    out["A_失去多数派"] = {
        "存活节点": 1, "集群规模": 3, "多数派要求": 2,
        "写请求结果": r.get("error") or r.get("result", {}).get("error"),
        "写请求耗时_ms": round(dt),
        "leader是否仍然自称leader": st2.get("state") == "leader",
        "提交下标是否前进": [before_commit, st2.get("commit_index")],
        "总余额（仍是5000说明没乱写）": sum(v["value"] for v in st2["kv"].values()),
    }
    print("A：只活 1 个节点，写入 %s，耗时 %.0fms，提交下标 %s→%s"
          % (r.get("error"), dt, before_commit, st2.get("commit_index")))

    # 恢复一个从节点，写立刻恢复
    c.start_node(followers[0])
    got = c.wait_caught_up(followers[0], timeout=15)
    t0 = time.time()
    r2 = c.client.transfer("A", "B", 100)
    out["A_恢复一个从节点"] = {
        "追平耗时_ms": round(got * 1000) if got is not None else None,
        "写入恢复": bool(r2.get("ok")),
        "恢复后写耗时_ms": round((time.time() - t0) * 1000),
        "总余额": c.total(),
    }
    print("A：恢复一个从节点后写入 %s，总余额 %s" % (r2.get("ok"), c.total()))

# ---------- B：quorum 改成 1 ----------
with Cluster("exp3b", base=7441, node_args=["--quorum", "1"]) as c:
    c.reset_accounts(1000)
    time.sleep(0.3)
    ld = c.leader()
    others = [i for i in range(1, 4) if i != ld]
    print("quorum=1 集群，初始 leader=%d" % ld)

    before = c.kv_of(ld)
    c.partition([[ld], others])
    time.sleep(1.2)   # 等另一侧选出自己的 leader

    sideA = ld
    sideB = None
    for i in others:
        st = c.status(i)
        if st.get("state") == "leader":
            sideB = i
            break

    def write_to(node, msg):
        return kvclient.rpc(c.ports[node - 1], msg, 5.0)

    ra = write_to(sideA, {"type": "client", "op": "transfer", "from": "A", "to": "B",
                          "amount": 200, "req_id": "splitA-" + uuid.uuid4().hex[:6]})
    # 再写一个只存在于 A 侧的标记 key：恢复后它如果消失，就是最直接的"数据丢了"
    write_to(sideA, {"type": "client", "op": "set", "key": "订单-001", "value": 1,
                     "req_id": "splitA-mark-" + uuid.uuid4().hex[:6]})
    rb = write_to(sideB, {"type": "client", "op": "transfer", "from": "D", "to": "E",
                          "amount": 300, "req_id": "splitB-" + uuid.uuid4().hex[:6]})
    kvA = c.kv_of(sideA)
    kvB = c.kv_of(sideB)

    out["B_quorum等于1"] = {
        "分区": "%s | %s" % ([sideA], others),
        "两侧是否各自有leader": sideB is not None,
        "A侧(节点%d)写结果" % sideA: {"ok": ra.get("ok"),
                                  "余额": {k: v["value"] for k, v in kvA.items()}},
        "B侧(节点%d)写结果" % sideB: {"ok": rb.get("ok"),
                                  "余额": {k: v["value"] for k, v in kvB.items()}},
        "分区期间两侧账本是否不同": kvA != kvB,
        "A侧是否写入了标记key": "订单-001" in kvA,
    }
    print("B：A侧 A→B 200 成功=%s；B侧 D→E 300 成功=%s；两侧账本不同=%s"
          % (ra.get("ok"), rb.get("ok"), kvA != kvB))

    c.heal()
    time.sleep(2.0)
    fin = c.leader()
    final_kv = c.kv_of(fin)
    final_total = sum(v["value"] for v in final_kv.values() if isinstance(v.get("value"), int))
    lost = {k: (kvA[k]["value"], final_kv.get(k, {}).get("value"))
            for k in kvA if k in kvA and (k not in final_kv
                                          or final_kv[k]["value"] != kvA[k]["value"])}
    out["B_quorum等于1"]["恢复后"] = {
        "最终leader": fin,
        "最终账本": {k: v["value"] for k, v in final_kv.items()},
        "A侧标记key是否还在": "订单-001" in final_kv,
        "被覆盖或消失的key(原值,现值)": lost,
        "客户已收到成功响应但结果丢失": bool(lost),
    }
    print("B：恢复网络后 leader=%s，A 侧标记 key 还在=%s，被覆盖的写入=%s"
          % (fin, "订单-001" in final_kv, lost))

print()
for k, v in out.items():
    if k != "实验":
        print("  %-16s %s" % (k, v))
save("exp3_quorum", out)
