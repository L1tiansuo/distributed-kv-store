#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集群管理器 + 网页控制台。

职责：
  1. 用子进程拉起 / 杀掉 / 重启 3 个节点（杀掉就是真杀，模拟突然宕机）
  2. 提供 HTTP API 给网页：查状态、提交操作、注入故障、跑压测
  3. 把每次操作记进事件时间线，方便现场讲解"刚才发生了什么"
"""
import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import client as kvclient  # noqa: E402

STATE = {
    "ports": [],
    "procs": {},
    "events": [],
    "started": time.time(),
    "data_dir": "",
}
LOCK = threading.Lock()


def now_str():
    return time.strftime("%H:%M:%S", time.localtime())


def event(text, kind="info"):
    with LOCK:
        STATE["events"].append({"t": now_str(), "text": text, "kind": kind,
                                "ts": time.time()})
        if len(STATE["events"]) > 300:
            del STATE["events"][0:100]
    print("[%s] %s" % (now_str(), text), flush=True)


# ---------------- 进程管理 ----------------
def node_ports():
    return STATE["ports"]


def peers_arg():
    return ",".join("%d@%d" % (i + 1, p) for i, p in enumerate(node_ports()))


def node_dir(i):
    return os.path.join(STATE["data_dir"], "node%d" % i)


def pid_path(i):
    return os.path.join(STATE["data_dir"], "node%d" % i, "node.pid")


def kill_pid(pid):
    """强制结束一个残留进程（Windows 用 taskkill，其它平台用 SIGKILL）。"""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=5)
        else:
            os.kill(pid, 9)
        return True
    except Exception:
        return False


def clean_stale(i):
    """上次如果被强杀，子进程会留在后台占着端口。启动前按 pid 文件清理掉。"""
    path = pid_path(i)
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
    except Exception:
        return
    if pid <= 0 or pid == os.getpid():
        return
    if kill_pid(pid):
        event("清理上次残留的节点 %d 进程（pid %d）" % (i, pid), "warn")
    try:
        os.remove(path)
    except Exception:
        pass


def start_node(i, extra=None):
    if i in STATE["procs"] and STATE["procs"][i].poll() is None:
        return
    os.makedirs(node_dir(i), exist_ok=True)
    logf = open(os.path.join(node_dir(i), "stdout.log"), "ab")
    argv = [sys.executable, os.path.join(HERE, "node.py"),
            "--id", str(i), "--port", str(node_ports()[i - 1]),
            "--peers", peers_arg(), "--data", node_dir(i)]
    if extra:
        argv += extra
    p = subprocess.Popen(argv, stdout=logf, stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    STATE["procs"][i] = p
    try:
        with open(pid_path(i), "w", encoding="utf-8") as f:
            f.write(str(p.pid))
    except Exception:
        pass
    event("启动节点 %d（进程 %d）" % (i, p.pid))


def kill_node(i):
    p = STATE["procs"].get(i)
    if p and p.poll() is None:
        p.kill()          # 真杀，不带 SIGTERM 优雅退出，模拟突然断电
        try:
            p.wait(timeout=3)
        except Exception:
            pass
        event("杀掉节点 %d（进程 %d）" % (i, p.pid), "warn")
        return True
    return False


def restart_node(i):
    kill_node(i)
    time.sleep(0.2)
    start_node(i)
    event("重启节点 %d" % i)


def stop_all():
    for i in list(STATE["procs"].keys()):
        p = STATE["procs"][i]
        if p.poll() is None:
            p.kill()
    STATE["procs"].clear()


# ---------------- 查询 ----------------
def node_status(i):
    try:
        st = kvclient.rpc(node_ports()[i - 1], {"type": "status"}, 0.4)
        st["alive"] = True
        return st
    except Exception:
        return {"ok": False, "alive": False, "node": i}


def cluster_snapshot():
    with LOCK:
        procs_alive = {i: (p.poll() is None) for i, p in STATE["procs"].items()}
    nodes = []
    ths = []
    out = {}

    def work(i):
        out[i] = node_status(i)

    for i in range(1, len(node_ports()) + 1):
        # 进程已经死了就别去连它：connect 会一直卡到超时，页面刷新会被拖慢
        if not procs_alive.get(i, False):
            out[i] = {"ok": False, "alive": False, "node": i}
            continue
        t = threading.Thread(target=work, args=(i,))
        t.start()
        ths.append(t)
    for t in ths:
        t.join()
    leader = None
    for i in range(1, len(node_ports()) + 1):
        st = out.get(i, {"alive": False})
        st["process_alive"] = procs_alive.get(i, False)
        if st.get("state") == "leader":
            leader = i
        nodes.append(st)
    # 以 leader 的账本作为"对外真实值"
    truth = {}
    for st in nodes:
        if st.get("state") == "leader" and st.get("kv"):
            truth = st["kv"]
            break
    total = sum(v["value"] for v in truth.values()) if truth else None
    with LOCK:
        events = STATE["events"][-60:]
    return {"nodes": nodes, "leader": leader, "truth": truth, "total": total,
            "events": events, "ports": node_ports()}


def op_execute(body):
    """在集群上执行一次业务操作。"""
    c = kvclient.Client(node_ports())
    op = body.get("op")
    t0 = time.perf_counter()
    if op == "transfer":
        r = c.transfer(body["from"], body["to"], int(body["amount"]),
                       req_id=body.get("req_id"), retries=int(body.get("retries", 2)))
    elif op == "set":
        r = c.set(body["key"], body.get("value"), req_id=body.get("req_id"))
    elif op == "cas":
        r = c.cas(body["key"], int(body["expect_version"]), body.get("value"),
                  req_id=body.get("req_id"))
    elif op == "get":
        r = c.get(body["key"], body.get("consistency", "linearizable"))
    elif op == "reset":
        accts = body.get("accounts") or {k: int(body.get("amount", 1000))
                                        for k in ("A", "B", "C", "D", "E")}
        r = c.reset(accts)
    elif op == "repeat_transfer":
        # 同一个 req_id 连发 n 次：用来演示幂等
        rid = c.new_req_id()
        rs = [c.transfer(body["from"], body["to"], int(body["amount"]), req_id=rid)
              for _ in range(int(body.get("times", 3)))]
        r = {"ok": True, "attempts": rs,
             "applied_count": sum(1 for x in rs if x.get("ok") and x.get("result", {}).get("ok")
                                  and not x.get("result", {}).get("duplicate"))}
    else:
        r = {"ok": False, "error": "unknown_op"}
    r["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return r


def do_partition(groups):
    """
    按分组制造双向网络分区。groups 形如 [[1],[2,3]]：
    每组只和本组的节点通信，跨组消息丢弃。
    """
    allnodes = list(range(1, len(node_ports()) + 1))
    if (not isinstance(groups, list) or
            not all(isinstance(g, list) for g in groups) or
            not all(isinstance(x, int) for g in groups for x in g)):
        raise ValueError("groups 必须是二维数组，例如 [[1],[2,3]]")
    for i in allnodes:
        my_group = next((g for g in groups if i in g), [i])
        blocked = [j for j in allnodes if j not in my_group]
        try:
            kvclient.rpc(node_ports()[i - 1], {"type": "admin", "cmd": "partition",
                                               "block": blocked}, 0.5)
        except Exception:
            # 节点已宕机就跳过：它本来就不在网络上，不需要再隔离一次
            pass
    event("制造网络分区 %s" % json.dumps(groups), "warn")


def do_heal():
    for i in range(1, len(node_ports()) + 1):
        try:
            kvclient.rpc(node_ports()[i - 1], {"type": "admin", "cmd": "heal"}, 0.5)
        except Exception:
            pass
    event("恢复网络（清除所有分区/延迟/重复注入）", "good")


def admin_apply(target, body):
    ids = list(range(1, len(node_ports()) + 1)) if target == "all" else [int(target)]
    out = []
    for i in ids:
        try:
            out.append(kvclient.rpc(node_ports()[i - 1], body, 0.8))
        except Exception as ex:
            out.append({"ok": False, "node": i, "error": str(ex)})
    return out


def bench(body):
    n = int(body.get("n", 200))
    keys_mode = body.get("keys", "multi")
    conc = int(body.get("concurrency", 4))
    client_ports = node_ports()
    keys = ["HOT"] if keys_mode == "single" else ["K%d" % i for i in range(50)]
    lat = []
    errs = [0]
    lk = threading.Lock()

    def worker(cnt):
        c = kvclient.Client(client_ports, timeout=10)
        for i in range(cnt):
            k = keys[i % len(keys)]
            t0 = time.perf_counter()
            r = c.set(k, i)
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

    res = {"requests": len(lat) + errs[0], "ok": len(lat), "errors": errs[0],
           "duration_s": round(dur, 3), "throughput": round(len(lat) / dur, 1) if dur else 0,
           "p50_ms": q(0.50), "p95_ms": q(0.95), "p99_ms": q(0.99),
           "max_ms": round(lat[-1], 1) if lat else None,
           "keys": keys_mode, "concurrency": conc}
    event("压测 %d 次（%s key，并发%d）：%.1f ops/s，p99=%sms"
          % (n, keys_mode, conc, res["throughput"], res["p99_ms"]))
    return res


def tail_log(i, n=80):
    path = os.path.join(node_dir(i), "stdout.log")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return [ln.rstrip("\n") for ln in lines[-n:]]


# ---------------- HTTP ----------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            with open(os.path.join(HERE, "console.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
            return
        if path == "/api/cluster":
            self._send(200, cluster_snapshot())
            return
        if path == "/api/logs":
            qs = self.path.split("?")[1] if "?" in self.path else ""
            nid = 1
            for part in qs.split("&"):
                if part.startswith("node="):
                    nid = int(part.split("=")[1])
            self._send(200, {"node": nid, "lines": tail_log(nid)})
            return
        self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        try:
            self._do_post()
        except Exception:
            import traceback
            tb = traceback.format_exc()
            sys.stderr.write(tb)
            event("接口异常：%s" % tb.strip().splitlines()[-1], "warn")
            try:
                self._send(500, {"ok": False, "error": tb.strip().splitlines()[-1],
                                 "detail": tb})
            except Exception:
                pass

    def _do_post(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            body = {}
        path = self.path.split("?")[0]

        if path == "/api/op":
            r = op_execute(body)
            if body.get("op") == "repeat_transfer":
                event("同一 req_id 连发 %d 次转账，实际生效 %s 次"
                      % (body.get("times", 3), r.get("applied_count")), "good")
            elif body.get("op") in ("transfer", "set", "cas", "reset"):
                ok = r.get("ok")
                detail = r.get("result", {}).get("error") or r.get("error") or ""
                event("%s → %s %s" % (body.get("op"), "成功" if ok else "失败", detail),
                      "good" if ok else "warn")
            self._send(200, r)
            return

        if path == "/api/partition":
            try:
                do_partition(body.get("groups") or [[1], [2, 3]])
            except ValueError as ex:
                self._send(400, {"ok": False, "error": str(ex)})
                return
            self._send(200, {"ok": True})
            return

        if path == "/api/heal":
            do_heal()
            self._send(200, {"ok": True})
            return

        if path == "/api/admin":
            out = admin_apply(body.get("target", "all"), body)
            if body.get("cmd") == "delay":
                event("给节点 %s 注入 %sms 消息延迟" % (body.get("target"), body.get("ms")))
            elif body.get("cmd") == "dup":
                event("给节点 %s 注入消息重复 ×%s" % (body.get("target"), body.get("n")))
            elif body.get("cmd") == "clock":
                event("把节点 %s 的时钟偏移 %sms" % (body.get("target"), body.get("delta_ms")))
            self._send(200, {"ok": True, "results": out})
            return

        if path == "/api/node":
            i = int(body.get("id"))
            action = body.get("action")
            if action == "kill":
                kill_node(i)
            elif action == "start":
                start_node(i)
            elif action == "restart":
                restart_node(i)
            self._send(200, {"ok": True})
            return

        if path == "/api/killleader":
            snap = cluster_snapshot()
            if snap["leader"]:
                kill_node(snap["leader"])
                self._send(200, {"ok": True, "killed": snap["leader"]})
            else:
                self._send(200, {"ok": False, "error": "没有 leader"})
            return

        if path == "/api/bench":
            self._send(200, bench(body))
            return

        if path == "/api/reset_data":
            stop_all()
            time.sleep(0.3)
            if os.path.isdir(STATE["data_dir"]):
                shutil.rmtree(STATE["data_dir"], ignore_errors=True)
            os.makedirs(STATE["data_dir"], exist_ok=True)
            event("清空所有节点数据目录")
            for i in range(1, len(node_ports()) + 1):
                start_node(i)
            self._send(200, {"ok": True})
            return

        self._send(404, {"ok": False, "error": "not_found"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", type=int, default=3)
    ap.add_argument("--base-port", type=int, default=7301)
    ap.add_argument("--console-port", type=int, default=8080)
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    ap.add_argument("--fresh", action="store_true", help="启动前清空数据目录")
    ap.add_argument("--node-args", default="", help="透传给节点的额外参数，如 --nosync")
    args = ap.parse_args()

    STATE["ports"] = [args.base_port + i for i in range(args.nodes)]
    STATE["data_dir"] = args.data
    os.makedirs(args.data, exist_ok=True)
    if args.fresh and os.path.isdir(args.data):
        shutil.rmtree(args.data, ignore_errors=True)
        os.makedirs(args.data, exist_ok=True)

    extra = args.node_args.split() if args.node_args else None
    for i in range(1, args.nodes + 1):
        clean_stale(i)
    for i in range(1, args.nodes + 1):
        start_node(i, extra)
    event("集群已启动：%d 个节点，端口 %s" % (args.nodes, STATE["ports"]), "good")

    srv = ThreadingHTTPServer(("127.0.0.1", args.console_port), Handler)
    srv.daemon_threads = True
    print("控制台: http://127.0.0.1:%d" % args.console_port, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_all()


if __name__ == "__main__":
    main()
