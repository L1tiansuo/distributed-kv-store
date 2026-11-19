#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验脚手架：每个实验自己在独立端口起一套 3 节点集群，跑完销毁，互不干扰。
测的是真实进程、真实 TCP、真实 fsync，不是模拟器。
"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
import client as kvclient  # noqa: E402

RESULTS = os.path.join(ROOT, "results")


def ensure_results():
    os.makedirs(RESULTS, exist_ok=True)


def save(name, data):
    ensure_results()
    path = os.path.join(RESULTS, name + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("→ 结果已写入 %s" % path)
    return path


class Cluster:
    def __init__(self, name, n=3, base=7401, node_args=None, fresh=True):
        self.name = name
        self.n = n
        self.ports = [base + i for i in range(n)]
        self.data = os.path.join(ROOT, "data_exp", name)
        self.node_args = list(node_args or [])
        self.procs = {}
        if fresh and os.path.isdir(self.data):
            shutil.rmtree(self.data, ignore_errors=True)
        os.makedirs(self.data, exist_ok=True)
        self.client = kvclient.Client(self.ports, timeout=6.0)

    # ---------- 进程 ----------
    def peers(self):
        return ",".join("%d@%d" % (i + 1, p) for i, p in enumerate(self.ports))

    def start_node(self, i):
        d = os.path.join(self.data, "node%d" % i)
        os.makedirs(d, exist_ok=True)
        logf = open(os.path.join(d, "stdout.log"), "ab")
        argv = [sys.executable, os.path.join(SRC, "node.py"),
                "--id", str(i), "--port", str(self.ports[i - 1]),
                "--peers", self.peers(), "--data", d] + self.node_args
        self.procs[i] = subprocess.Popen(argv, stdout=logf, stderr=subprocess.STDOUT,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def start(self, wait_leader=True):
        for i in range(1, self.n + 1):
            self.start_node(i)
        if wait_leader:
            self.wait_leader()
        return self

    def kill(self, i):
        p = self.procs.get(i)
        if p and p.poll() is None:
            p.kill()
            try:
                p.wait(timeout=3)
            except Exception:
                pass

    def stop(self):
        for i in list(self.procs):
            self.kill(i)
        self.procs.clear()

    # ---------- 查询 ----------
    def status(self, i, timeout=0.5):
        try:
            return kvclient.rpc(self.ports[i - 1], {"type": "status"}, timeout)
        except Exception:
            return {"ok": False, "node": i, "state": "dead"}

    def alive_procs(self):
        return [i for i, p in self.procs.items() if p.poll() is None]

    def all_status(self):
        return [self.status(i) for i in range(1, self.n + 1)]

    def leader(self):
        best = None
        for st in self.all_status():
            if st.get("state") == "leader":
                if best is None or st["term"] > best["term"]:
                    best = st
        return best["node"] if best else None

    def wait_leader(self, timeout=10.0, min_term=0):
        """
        只轮询"进程还活着"的节点，且用 0.12s 短超时。
        否则对一个刚被 kill 的端口做 connect 会一直卡到超时，
        测出来的"选主耗时"里混进了探测开销 —— 这一点在报告里要写清楚。
        """
        t0 = time.time()
        while time.time() - t0 < timeout:
            for i in self.alive_procs():
                st = self.status(i, 0.12)
                if st.get("state") == "leader" and st.get("term", 0) >= min_term:
                    return i, time.time() - t0
            time.sleep(0.005)
        raise TimeoutError("没有选出 leader")

    def wait_until(self, fn, timeout=10.0, interval=0.02):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if fn():
                return time.time() - t0
            time.sleep(interval)
        return None

    def wait_caught_up(self, node, timeout=15.0):
        """等某个节点把日志追平到 leader。"""
        def done():
            ld = self.leader()
            if ld is None:
                return False
            a = self.status(ld).get("commit_index", 0)
            b = self.status(node).get("commit_index", 0)
            return b >= a
        return self.wait_until(done, timeout)

    # ---------- 便捷操作 ----------
    def admin(self, target, body):
        ids = range(1, self.n + 1) if target == "all" else [int(target)]
        out = []
        for i in ids:
            try:
                out.append(kvclient.rpc(self.ports[i - 1], body, 2.0))
            except Exception as ex:
                out.append({"ok": False, "error": str(ex)})
        return out

    def partition(self, groups):
        alln = list(range(1, self.n + 1))
        for i in alln:
            mine = next((g for g in groups if i in g), [i])
            self.admin(i, {"type": "admin", "cmd": "partition",
                           "block": [j for j in alln if j not in mine]})

    def heal(self):
        self.admin("all", {"type": "admin", "cmd": "heal"})

    def reset_accounts(self, amount=1000):
        return self.client.reset({k: amount for k in ("A", "B", "C", "D", "E")})

    def total(self):
        ld = self.leader()
        if ld is None:
            return None
        st = self.status(ld)
        return sum(v["value"] for v in st.get("kv", {}).values())

    def kv_of(self, node):
        return self.status(node).get("kv", {})

    def log_len(self, node):
        return self.status(node).get("log_len", 0)

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.stop()


def replicas_identical(cluster):
    """所有存活节点的账本是否完全一致（慢节点可能落后，用 wait 先等齐）。"""
    kvs = []
    for st in cluster.all_status():
        if st.get("state") == "dead" or not st.get("ok"):
            continue
        kvs.append(json.dumps(st.get("kv", {}), sort_keys=True))
    return len(set(kvs)) == 1, kvs
