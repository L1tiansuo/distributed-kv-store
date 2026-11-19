#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""客户端库 + 命令行。所有写请求都带 req_id，超时后用同一个 req_id 重试，靠服务端幂等表去重。"""
import argparse
import json
import os
import socket
import threading
import sys
import time
import uuid

DEFAULT_PORTS = [7301, 7302, 7303]


def rpc(port, msg, timeout=5.0):
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    try:
        s.sendall((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        return json.loads(buf.decode("utf-8"))
    finally:
        s.close()


class Endpoint:
    """到一个节点的长连接。压测时每秒上千次请求，每次重连 TCP 会把账算错在客户端头上。"""

    def __init__(self, port, timeout=5.0):
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.rfile = None
        self.lock = threading.Lock()

    def _connect(self, timeout):
        s = socket.create_connection(("127.0.0.1", self.port), timeout=timeout)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock = s
        self.rfile = s.makefile("rb")

    def close(self):
        for f in (self.rfile, self.sock):
            try:
                if f:
                    f.close()
            except Exception:
                pass
        self.sock = None
        self.rfile = None

    def call(self, msg, timeout=None):
        timeout = timeout or self.timeout
        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        with self.lock:
            for attempt in (0, 1):
                try:
                    if self.sock is None:
                        self._connect(timeout)
                    self.sock.settimeout(timeout)
                    self.sock.sendall(data)
                    line = self.rfile.readline()
                    if not line:
                        raise ConnectionError("closed by peer")
                    return json.loads(line.decode("utf-8"))
                except Exception:
                    self.close()
                    if attempt == 1:
                        raise
        return None


class Client:
    def __init__(self, ports=None, timeout=5.0):
        self.ports = ports or DEFAULT_PORTS
        self.timeout = timeout
        self.client_id = uuid.uuid4().hex[:8]
        self.leader_port = None   # 客户端缓存 leader，避免每次请求都探测三跳
        self.conns = {p: Endpoint(p, timeout) for p in self.ports}

    def _rpc(self, port, msg, timeout=None):
        return self.conns[port].call(msg, timeout)

    # ---- 找 leader ----
    def discover(self):
        best = None
        for p in self.ports:
            try:
                st = self._rpc(p, {"type": "status"}, 1.0)
            except Exception:
                continue
            if st.get("state") == "leader":
                self.leader_port = p
                return p
            if best is None:
                best = p
        return best

    def call(self, msg, retries=3, timeout=None):
        """发送一条请求，遇到 not_leader 就跟着 leader 提示走，遇到超时就重试。"""
        timeout = timeout or self.timeout
        target = self.leader_port or self.discover()
        last = None
        for _ in range(retries):
            if target is None:
                target = self.discover()
            try:
                resp = self._rpc(target, msg, timeout)
            except Exception as ex:
                last = {"ok": False, "error": "connection: %s" % ex}
                target = self.discover()
                continue
            last = resp
            if resp.get("ok"):
                self.leader_port = target
                return resp
            if resp.get("error") not in ("not_leader", "timeout_unknown", "timeout_read"):
                return resp
            hint = resp.get("leader")
            if hint:
                target = self.ports[hint - 1] if 0 <= hint - 1 < len(self.ports) else None
            else:
                target = self.discover()
        return last or {"ok": False, "error": "no_leader"}

    # ---- 业务接口 ----
    def get(self, key, consistency="linearizable"):
        # 读请求不带 req_id（幂等性对只读无意义），但不许重试到把旧值当新值
        return self.call({"type": "client", "op": "get", "key": key,
                          "consistency": consistency}, retries=2)

    def reset(self, accounts):
        return self.call({"type": "client", "op": "reset", "accounts": accounts,
                          "req_id": "reset-" + uuid.uuid4().hex})

    def set(self, key, value, req_id=None):
        return self.call({"type": "client", "op": "set", "key": key, "value": value,
                          "req_id": req_id or self.new_req_id()})

    def cas(self, key, expect_version, value, req_id=None):
        return self.call({"type": "client", "op": "cas", "key": key,
                          "expect_version": expect_version, "value": value,
                          "req_id": req_id or self.new_req_id()})

    def transfer(self, src, dst, amount, req_id=None, retries=3):
        return self.call({"type": "client", "op": "transfer", "from": src, "to": dst,
                          "amount": amount, "req_id": req_id or self.new_req_id()},
                         retries=retries)

    def raw_write(self, msg, req_id=None, retries=3):
        msg = dict(msg)
        msg["req_id"] = req_id or self.new_req_id()
        return self.call(msg, retries=retries)

    def new_req_id(self):
        return "%s-%s" % (self.client_id, uuid.uuid4().hex[:10])

    def status_all(self):
        out = []
        for p in self.ports:
            try:
                out.append(rpc(p, {"type": "status"}, 1.0))
            except Exception:
                out.append({"ok": False, "port": p})
        return out


def main():
    ap = argparse.ArgumentParser(description="KV Store 客户端")
    ap.add_argument("--ports", default=",".join(str(p) for p in DEFAULT_PORTS))
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    p_reset = sub.add_parser("reset")
    p_reset.add_argument("--amount", type=int, default=1000)

    p_get = sub.add_parser("get")
    p_get.add_argument("key")
    p_get.add_argument("--stale", action="store_true")

    p_set = sub.add_parser("set")
    p_set.add_argument("key")
    p_set.add_argument("value", type=int)

    p_cas = sub.add_parser("cas")
    p_cas.add_argument("key")
    p_cas.add_argument("expect", type=int)
    p_cas.add_argument("value", type=int)

    p_tr = sub.add_parser("transfer")
    p_tr.add_argument("src")
    p_tr.add_argument("dst")
    p_tr.add_argument("amount", type=int)
    p_tr.add_argument("--times", type=int, default=1, help="用同一个 req_id 重复发几次")
    p_tr.add_argument("--fresh", action="store_true", help="每次都用新的 req_id（不幂等）")

    p_bench = sub.add_parser("bench")
    p_bench.add_argument("--n", type=int, default=200)
    p_bench.add_argument("--keys", default="single", choices=["single", "multi"])
    p_bench.add_argument("--concurrency", type=int, default=1)

    args = ap.parse_args()
    ports = [int(x) for x in args.ports.split(",")]
    c = Client(ports)

    if args.cmd == "status":
        for st in c.status_all():
            print(json.dumps(st, ensure_ascii=False, indent=2))
        return

    if args.cmd == "reset":
        accounts = {"A": args.amount, "B": args.amount, "C": args.amount,
                    "D": args.amount, "E": args.amount}
        print(json.dumps(c.reset(accounts), ensure_ascii=False))
        return

    if args.cmd == "get":
        r = c.get(args.key, "stale" if args.stale else "linearizable")
        print(json.dumps(r, ensure_ascii=False))
        return

    if args.cmd == "set":
        print(json.dumps(c.set(args.key, args.value), ensure_ascii=False))
        return

    if args.cmd == "cas":
        print(json.dumps(c.cas(args.key, args.expect, args.value), ensure_ascii=False))
        return

    if args.cmd == "transfer":
        req_id = c.new_req_id()
        results = []
        for i in range(args.times):
            rid = c.new_req_id() if args.fresh else req_id
            r = c.transfer(args.src, args.dst, args.amount, req_id=rid)
            results.append(r)
            print("第%d次: %s" % (i + 1, json.dumps(r, ensure_ascii=False)))
        print("--- 最终余额 ---")
        for k in ("A", "B", "C", "D", "E"):
            print(k, json.dumps(c.get(k), ensure_ascii=False))
        return

    if args.cmd == "bench":
        import threading
        keys = ["HOT"] if args.keys == "single" else ["K%d" % i for i in range(50)]
        lat, errs = [], [0]
        lock = threading.Lock()

        def worker(n):
            for i in range(n):
                k = keys[i % len(keys)]
                t0 = time.perf_counter()
                r = c.set(k, i)
                dt = (time.perf_counter() - t0) * 1000
                with lock:
                    if r.get("ok"):
                        lat.append(dt)
                    else:
                        errs[0] += 1

        per = args.n // args.concurrency
        t0 = time.perf_counter()
        ths = [threading.Thread(target=worker, args=(per,)) for _ in range(args.concurrency)]
        [t.start() for t in ths]
        [t.join() for t in ths]
        dur = time.perf_counter() - t0
        lat.sort()
        if lat:
            def q(p):
                return round(lat[min(len(lat) - 1, int(len(lat) * p))], 1)
            print(json.dumps({
                "requests": len(lat) + errs[0], "ok": len(lat), "errors": errs[0],
                "duration_s": round(dur, 3), "throughput": round(len(lat) / dur, 1),
                "p50_ms": q(0.50), "p95_ms": q(0.95), "p99_ms": q(0.99),
                "max_ms": round(lat[-1], 1),
            }, ensure_ascii=False))


if __name__ == "__main__":
    main()
