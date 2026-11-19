#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KV Store 单节点实现：Raft 风格日志复制 + 账户状态机。

线程模型（这是报告里"架构"一节要画的东西）：
  1. RPC 服务线程：每个入站连接一个短线程，读一行 JSON、处理、写一行 JSON、关闭。
  2. 定时器线程：检查选举超时、把已提交日志应用到状态机、推进读请求。
  3. 每个对等节点的发送线程：心跳 + 日志复制，阻塞式 RPC 带超时。
  4. 选举线程：只在一次选举存活，并发向其他节点拉票。

一把大锁（self.cv 的底层锁）保护所有状态。状态机严格按日志下标顺序应用，
因此"一条日志项 = 一笔原子事务"天然成立，不需要两阶段提交。
"""
import argparse
import json
import os
import random
import socket
import sys
import threading
import time
from collections import OrderedDict

# ---------------- 时间参数 ----------------
HEARTBEAT = 0.10          # 心跳间隔（秒）
ELECTION_MIN = 0.35       # 选举超时下限，必须远大于心跳
ELECTION_MAX = 0.65       # 选举超时上限
RPC_TIMEOUT = 0.35        # 单次 RPC 超时
REQUEST_TIMEOUT = 3.0     # 客户端写请求等待提交的总时长
DEDUP_CAP = 5000          # 幂等表容量


def log_line(level, msg):
    ts = time.strftime("%H:%M:%S", time.localtime())
    sys.stdout.write("%s [%s] %s\n" % (ts, level, msg))
    sys.stdout.flush()


class PeerClient:
    """到某个对等节点的长连接客户端。复用连接是为了避免每 100ms 建一次 TCP。"""

    def __init__(self, addr):
        self.addr = addr
        self.sock = None
        self.lock = threading.Lock()
        self.rfile = None

    def _connect(self, timeout):
        s = socket.create_connection(self.addr, timeout=timeout)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock = s
        self.rfile = s.makefile("rb")

    def close(self):
        try:
            if self.rfile:
                self.rfile.close()
        except Exception:
            pass
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None
        self.rfile = None

    def call(self, msg, timeout=RPC_TIMEOUT):
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
                        raise ConnectionError("peer closed")
                    return json.loads(line.decode("utf-8"))
                except Exception:
                    self.close()
                    if attempt == 1:
                        raise
        return None


class Node:
    def __init__(self, node_id, port, peer_map, data_dir, quorum=None, fsync=True,
                 bind="127.0.0.1"):
        self.id = node_id
        self.port = port
        self.bind = bind
        self.peer_ids = [p for p in peer_map if p != node_id]
        self.peers = {p: PeerClient(peer_map[p]) for p in self.peer_ids}
        self.data_dir = data_dir
        self.fsync = fsync
        self.quorum_override = quorum

        # ---- Raft 持久状态 ----
        self.current_term = 0
        self.voted_for = None
        self.log = [{"term": 0, "index": 0}]   # 下标 0 是哨兵
        self.commit_index = 0

        # ---- Raft 易失状态 ----
        self.state = "follower"
        self.leader_id = None
        self.votes = set()
        self.next_index = {}
        self.match_index = {}
        self.election_deadline = time.monotonic() + random.uniform(ELECTION_MIN, ELECTION_MAX)

        # ---- 状态机 ----
        self.last_applied = 0
        self.kv = {}                 # key -> {"value": int, "version": int}
        self.dedup = OrderedDict()   # req_id -> 业务结果（随日志一起复制）
        self.waiters = {}            # 日志下标 -> 等待中的客户端

        # ---- 读请求 ----
        self.read_seq = 0
        self.pending_reads = {}      # rid -> {"target","acks","done","key","value"}
        self.allow_stale_read = False

        # ---- 故障注入开关 ----
        self.blocked = set()         # 被隔离的对等节点
        self.delay_ms = 0            # 出站消息延迟
        self.dup_extra = 0           # 出站消息重复次数
        self.clock_offset = 0        # 人为时钟偏移
        self.hlc = 0

        # ---- 统计 ----
        self.started_at = time.time()
        self.applied_total = 0
        self.reject_write = 0

        self.cv = threading.Condition(threading.RLock())
        self.stopping = False
        self.lockfile = os.path.join(self.data_dir, "node.lock")
        os.makedirs(self.data_dir, exist_ok=True)
        self.wal_path = os.path.join(self.data_dir, "log.jsonl")
        self.meta_path = os.path.join(self.data_dir, "meta.json")
        self.wal_fp = None
        self._load()

    # ================= 持久化 =================
    def _load(self):
        meta = {"term": 0, "voted_for": None, "commit_index": 0}
        if os.path.exists(self.meta_path):
            try:
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    meta.update(json.load(f))
            except Exception:
                pass
        self.current_term = meta.get("term", 0)
        self.voted_for = meta.get("voted_for")
        self.commit_index = meta.get("commit_index", 0)

        if os.path.exists(self.wal_path):
            with open(self.wal_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except Exception:
                        break   # 崩溃时最后一行可能是半条，直接丢弃
                    if e["index"] == len(self.log):
                        self.log.append(e)
        # 崩溃重启后，只回放"已提交"的部分；未提交的尾部保留待覆盖
        up_to = min(self.commit_index, len(self.log) - 1)
        for i in range(1, up_to + 1):
            self._apply_entry(self.log[i])
        self.last_applied = up_to
        self.commit_index = up_to
        log_line("BOOT", "节点%d 装载 term=%d 日志=%d条 已提交=%d 账户=%s"
                 % (self.id, self.current_term, len(self.log) - 1, up_to,
                    {k: v["value"] for k, v in self.kv.items()}))

    def _persist_meta(self, sync=True):
        """任期和投票必须立刻落盘（否则可能违反"一个任期只投一票"）；
        commit_index 只是恢复用的提示，落后是安全的，所以定时保存时不做 fsync ——
        实测那个 fsync 会在 Windows 上卡住写路径几十毫秒。"""
        tmp = self.meta_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"term": self.current_term, "voted_for": self.voted_for,
                       "commit_index": self.commit_index}, f)
            f.flush()
            if sync:
                os.fsync(f.fileno())
        os.replace(tmp, self.meta_path)

    def _append_wal(self, entry):
        if self.wal_fp is None:
            self.wal_fp = open(self.wal_path, "a", encoding="utf-8")
        self.wal_fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.wal_fp.flush()
        if self.fsync:
            os.fsync(self.wal_fp.fileno())

    def _rewrite_wal(self):
        """日志被截断时重写整个文件（Raft 里截断只在冲突时发生，很少）。"""
        if self.wal_fp:
            self.wal_fp.close()
            self.wal_fp = None
        tmp = self.wal_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for e in self.log[1:]:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
            f.flush()
            if self.fsync:
                os.fsync(f.fileno())
        os.replace(tmp, self.wal_path)

    # ================= 状态机 =================
    def _apply_entry(self, entry):
        """确定性应用。所有节点用同样的顺序执行，结果必然一致。"""
        result = self._exec_cmd(entry["cmd"])
        self.last_applied = entry["index"]
        self.applied_total += 1
        w = self.waiters.get(entry["index"])
        # 关键：必须确认"现在应用的这条"就是客户端当初写的那条。
        # 日志被新主截断后，同一个下标可能换成别的日志项（比如 noop），
        # 只按下标回填结果就会把 noop 的返回当成转账的返回。
        if w is not None and w["entry"] is entry:
            self.waiters.pop(entry["index"], None)
            w["done"] = True
            w["result"] = result
        return result

    def _exec_cmd(self, cmd):
        op = cmd.get("op")
        req_id = cmd.get("req_id")

        # 幂等：同一个 req_id 只执行一次，直接返回上次的结果。
        # 去重表放在状态机里（而不是 leader 内存里），主节点切换后依然生效。
        if req_id and req_id in self.dedup:
            self.dedup.move_to_end(req_id)
            return dict(self.dedup[req_id], duplicate=True)

        if op == "reset":
            self.kv = {}
            for k, v in cmd["accounts"].items():
                self.kv[k] = {"value": int(v), "version": 1}
            result = {"ok": True, "accounts": {k: v["value"] for k, v in self.kv.items()}}
        elif op == "set":
            k = cmd["key"]
            cur = self.kv.get(k)
            version = (cur["version"] + 1) if cur else 1
            self.kv[k] = {"value": cmd["value"], "version": version}
            result = {"ok": True, "key": k, "value": cmd["value"], "version": version}
        elif op == "cas":
            # 比较并交换：客户端带着"我以为的版本号"来，对不上就拒绝。
            k = cmd["key"]
            cur = self.kv.get(k)
            cur_ver = cur["version"] if cur else 0
            if cur_ver != cmd["expect_version"]:
                result = {"ok": False, "error": "version_conflict",
                          "expect_version": cmd["expect_version"], "actual_version": cur_ver}
            else:
                version = cur_ver + 1
                self.kv[k] = {"value": cmd["value"], "version": version}
                result = {"ok": True, "key": k, "value": cmd["value"], "version": version}
        elif op == "transfer":
            src, dst, amount = cmd["from"], cmd["to"], int(cmd["amount"])
            a, b = self.kv.get(src), self.kv.get(dst)
            if a is None or b is None:
                result = {"ok": False, "error": "account_not_found"}
            elif a["value"] < amount:
                result = {"ok": False, "error": "insufficient_funds",
                          "balance": a["value"], "amount": amount}
            else:
                # 两个账户在同一条日志项里一起改，要么都成，要么都不成
                a["value"] -= amount
                a["version"] += 1
                b["value"] += amount
                b["version"] += 1
                result = {"ok": True, "from": src, "to": dst, "amount": amount,
                          "balance_from": a["value"], "balance_to": b["value"],
                          "version_from": a["version"], "version_to": b["version"]}
        elif op == "noop":
            result = {"ok": True, "noop": True}
        else:
            result = {"ok": False, "error": "unknown_op"}

        if req_id:
            self.dedup[req_id] = result
            while len(self.dedup) > DEDUP_CAP:
                self.dedup.popitem(last=False)   # 先进先出淘汰，所有节点一致
        return result

    # ================= 状态迁移 =================
    def _abort_waiters(self):
        """一旦不再是 leader，本地那些还没提交的写入就不可能成功了，直接告诉客户端失败。"""
        for w in self.waiters.values():
            w["aborted"] = True
        self.waiters.clear()

    def _become_follower(self, term, leader=None):
        with self.cv:
            if term > self.current_term:
                self.current_term = term
                self.voted_for = None
                self._persist_meta()
            if self.state == "leader":
                self._abort_waiters()
            self.state = "follower"
            self.leader_id = leader
            self.election_deadline = time.monotonic() + random.uniform(ELECTION_MIN, ELECTION_MAX)
            self.cv.notify_all()

    def _start_election(self):
        with self.cv:
            if self.state == "leader":
                return
            self.current_term += 1
            term = self.current_term
            self.state = "candidate"
            self.voted_for = self.id
            self.leader_id = None
            self.votes = {self.id}
            self.election_deadline = time.monotonic() + random.uniform(ELECTION_MIN, ELECTION_MAX)
            self._persist_meta()
            msg = {"type": "request_vote", "from": self.id, "term": term,
                   "last_index": len(self.log) - 1, "last_term": self.log[-1]["term"]}
            log_line("VOTE", "节点%d 发起选举 term=%d" % (self.id, term))

        def ask(pid):
            try:
                resp = self.peers[pid].call(msg, RPC_TIMEOUT)
            except Exception:
                return
            with self.cv:
                if self.current_term != term or self.state != "candidate":
                    return
                if resp.get("term", 0) > self.current_term:
                    self.current_term = resp["term"]
                    self.voted_for = None
                    self._persist_meta()
                    self.state = "follower"
                    self.leader_id = None
                    return
                if resp.get("vote_granted"):
                    self.votes.add(pid)
                    if len(self.votes) >= self.quorum_size():
                        self._become_leader()

        for p in self.peer_ids:
            threading.Thread(target=ask, args=(p,), daemon=True).start()

    def _become_leader(self):
        if self.state == "leader":
            return
        self.state = "leader"
        self.leader_id = self.id
        for p in self.peer_ids:
            self.next_index[p] = len(self.log)
            self.match_index[p] = 0
        log_line("LEAD", "节点%d 当选 leader term=%d" % (self.id, self.current_term))
        # 先提交一条 noop：把前任可能留下的、已复制到多数派但没来得及提交的日志一遍推进
        entry = {"term": self.current_term, "index": len(self.log), "cmd": {"op": "noop"}}
        self.log.append(entry)
        self._append_wal(entry)
        self._advance_commit()
        self.cv.notify_all()

    def quorum_size(self):
        if self.quorum_override:
            return self.quorum_override
        return (len(self.peer_ids) + 1) // 2 + 1

    def _advance_commit(self):
        """多数派都存了才算提交。这里只允许提交当前任期的日志（Raft 的安全性要求）。"""
        if self.state != "leader":
            return
        idxs = sorted([self.match_index.get(p, 0) for p in self.peer_ids] + [len(self.log) - 1],
                      reverse=True)
        need = self.quorum_size()
        if len(idxs) < need:
            return
        cand = idxs[need - 1]
        if cand > self.commit_index and self.log[cand]["term"] == self.current_term:
            self.commit_index = cand
            # 一提交就立刻应用并唤醒等待的客户端，不要等定时器下一轮
            self._apply_committed()
            self.cv.notify_all()

    # ================= 复制线程 =================
    def _peer_loop(self, pid):
        next_send = 0.0
        while not self.stopping:
            with self.cv:
                if self.state != "leader":
                    self.cv.wait(0.05)
                    continue
                now = time.monotonic()
                # 有未复制的日志就立刻发，不等心跳；只有空闲时才按心跳节奏走
                urgent = self.next_index.get(pid, len(self.log)) < len(self.log)
                if now < next_send and not urgent:
                    self.cv.wait(min(0.02, next_send - now))
                    continue
                next_send = now + HEARTBEAT
                if pid in self.blocked:
                    continue
                ni = max(1, min(self.next_index.get(pid, len(self.log)), len(self.log)))
                prev_index = ni - 1
                prev_term = self.log[prev_index]["term"]
                entries = [dict(e) for e in self.log[ni:]]
                msg = {"type": "append_entries", "from": self.id, "to": pid,
                       "term": self.current_term, "prev_index": prev_index,
                       "prev_term": prev_term, "entries": entries,
                       "leader_commit": self.commit_index}
            if self.delay_ms:
                time.sleep(self.delay_ms / 1000.0)   # 故障注入：消息在路上耽误
            try:
                resp = None
                for _ in range(1 + (self.dup_extra if msg["entries"] else 0)):
                    resp = self.peers[pid].call(msg, RPC_TIMEOUT)
            except Exception:
                continue
            self._on_append_reply(pid, msg, resp)

    def _on_append_reply(self, pid, msg, resp):
        if not resp:
            return
        with self.cv:
            if resp.get("term", 0) > self.current_term:
                self.current_term = resp["term"]
                self.voted_for = None
                self._persist_meta()
                if self.state == "leader":
                    self._abort_waiters()
                self.state = "follower"
                self.leader_id = None
                return
            if self.state != "leader" or resp.get("term") != self.current_term:
                return
            if resp.get("success"):
                mi = resp.get("match_index", msg["prev_index"])
                self.match_index[pid] = max(self.match_index.get(pid, 0), mi)
                self.next_index[pid] = self.match_index[pid] + 1
                for rd in self.pending_reads.values():
                    if not rd["done"]:
                        rd["acks"].add(pid)   # 这次应答同时是"我还是 leader"的证明
                self._advance_commit()
            else:
                hint = resp.get("conflict_index")
                self.next_index[pid] = max(1, hint if hint else self.next_index.get(pid, 1) - 1)
            self.cv.notify_all()

    # ================= 定时器 =================
    def _ticker(self):
        last_meta = 0.0
        while not self.stopping:
            with self.cv:
                now = time.monotonic()
                if self.state == "leader":
                    self._advance_commit()
                    self._apply_committed()
                    self._resolve_reads()
                    if now - last_meta > 0.2:
                        last_meta = now
                        try:
                            self._persist_meta(sync=False)
                        except Exception:
                            pass
                else:
                    self._apply_committed()
                    if now >= self.election_deadline:
                        self._start_election()
                self.cv.wait(0.02)

    def _apply_committed(self):
        while self.last_applied < self.commit_index:
            nxt = self.last_applied + 1
            if nxt >= len(self.log):
                break
            self._apply_entry(self.log[nxt])

    def _resolve_reads(self):
        need = self.quorum_size()
        for rid, rd in list(self.pending_reads.items()):
            if rd["done"]:
                continue
            if self.state != "leader" or rd["term"] != self.current_term:
                rd["done"] = True
                rd["error"] = "not_leader"
                self.pending_reads.pop(rid, None)
                continue
            if len(rd["acks"]) >= need and self.last_applied >= rd["target"]:
                rd["done"] = True
                v = self.kv.get(rd["key"])
                rd["value"] = (dict(v) if v else None)
                rd["index"] = self.last_applied
                self.pending_reads.pop(rid, None)

    # ================= 客户端请求 =================
    def client_write(self, cmd):
        with self.cv:
            if self.state != "leader":
                self.reject_write += 1
                return {"ok": False, "error": "not_leader", "leader": self.leader_id,
                        "term": self.current_term}
            # 快路径：这个 req_id 已经执行过，直接返回上次结果，日志不增长。
            # 慢路径才是状态机里那份"跟着日志复制"的去重表 —— 主切换后快路径失效，
            # 靠它兜底，这才是幂等真正的保证。
            rid = cmd.get("req_id")
            if rid and rid in self.dedup:
                return {"ok": True, "index": self.last_applied, "leader": self.id,
                        "result": dict(self.dedup[rid], duplicate=True)}
            entry = {"term": self.current_term, "index": len(self.log), "cmd": cmd}
            self.log.append(entry)
            try:
                self._append_wal(entry)
            except Exception as ex:
                self.log.pop()
                return {"ok": False, "error": "disk_error: %s" % ex}
            idx = entry["index"]
            waiter = {"done": False, "result": None, "entry": entry, "aborted": False}
            self.waiters[idx] = waiter
            self.cv.notify_all()
            deadline = time.monotonic() + REQUEST_TIMEOUT
            while not waiter["done"]:
                if waiter["aborted"]:
                    # 自己的日志被截断了，这条写入不可能再提交
                    return {"ok": False, "error": "not_leader", "leader": self.leader_id}
                left = deadline - time.monotonic()
                if left <= 0:
                    if self.state != "leader":
                        return {"ok": False, "error": "not_leader", "leader": self.leader_id}
                    # 已经写进本地日志但还没拿到多数派确认：结果对客户端是"未知"
                    return {"ok": False, "error": "timeout_unknown", "index": idx,
                            "leader": self.id}
                self.cv.wait(min(left, 0.05))
            return {"ok": True, "index": idx, "result": waiter["result"], "leader": self.id}

    def client_read(self, key, consistency="linearizable"):
        if consistency == "stale":
            with self.cv:
                v = self.kv.get(key)
                return {"ok": True, "result": (dict(v) if v else None),
                        "stale": True, "index": self.last_applied, "node": self.id}
        with self.cv:
            if self.state != "leader":
                return {"ok": False, "error": "not_leader", "leader": self.leader_id}
            self.read_seq += 1
            rid = self.read_seq
            target = self.commit_index
            rd = {"term": self.current_term, "target": target, "acks": {self.id},
                  "done": False, "key": key, "value": None, "index": target}
            self.pending_reads[rid] = rd
            self.cv.notify_all()
            deadline = time.monotonic() + REQUEST_TIMEOUT
            while not rd["done"]:
                left = deadline - time.monotonic()
                if left <= 0:
                    self.pending_reads.pop(rid, None)
                    return {"ok": False, "error": "timeout_read", "leader": self.id}
                self.cv.wait(min(left, 0.05))
            if rd.get("error"):
                return {"ok": False, "error": rd["error"], "leader": self.leader_id}
            return {"ok": True, "result": rd["value"], "index": rd["index"], "node": self.id}

    # ================= RPC 分发 =================
    def handle(self, msg):
        t = msg.get("type")
        if t == "append_entries":
            return self.on_append_entries(msg)
        if t == "request_vote":
            return self.on_request_vote(msg)
        if t == "client":
            op = msg.get("op")
            if op == "get":
                return self.client_read(msg.get("key"), msg.get("consistency", "linearizable"))
            return self.client_write(msg)
        if t == "status":
            return self.status()
        if t == "admin":
            return self.admin(msg)
        return {"ok": False, "error": "unknown_type"}

    def on_request_vote(self, msg):
        with self.cv:
            term = msg["term"]
            if term < self.current_term:
                return {"term": self.current_term, "vote_granted": False}
            if term > self.current_term:
                self.current_term = term
                self.voted_for = None
                if self.state == "leader":
                    self._abort_waiters()
                self.state = "follower"
                self._persist_meta()
            last_index, last_term = len(self.log) - 1, self.log[-1]["term"]
            up_to_date = (msg["last_term"] > last_term or
                          (msg["last_term"] == last_term and msg["last_index"] >= last_index))
            if (self.voted_for in (None, msg["from"])) and up_to_date:
                self.voted_for = msg["from"]
                self._persist_meta()
                self.election_deadline = time.monotonic() + random.uniform(ELECTION_MIN, ELECTION_MAX)
                return {"term": self.current_term, "vote_granted": True}
            return {"term": self.current_term, "vote_granted": False}

    def on_append_entries(self, msg):
        with self.cv:
            term = msg["term"]
            if term < self.current_term:
                return {"term": self.current_term, "success": False}
            if term > self.current_term:
                self.current_term = term
                self.voted_for = None
                self._persist_meta()
            was_leader = (self.state == "leader")
            self.state = "follower"
            self.leader_id = msg["from"]
            self.election_deadline = time.monotonic() + random.uniform(ELECTION_MIN, ELECTION_MAX)
            if was_leader:
                self._abort_waiters()   # 先记下新 leader，客户端被拒时能直接被指过去

            prev = msg["prev_index"]
            if prev > len(self.log) - 1:
                return {"term": self.current_term, "success": False,
                        "conflict_index": len(self.log)}
            if self.log[prev]["term"] != msg["prev_term"]:
                bad_term = self.log[prev]["term"]
                ci = prev
                while ci > 1 and self.log[ci - 1]["term"] == bad_term:
                    ci -= 1
                return {"term": self.current_term, "success": False, "conflict_index": ci}

            entries = msg["entries"]
            rewritten = False
            for e in entries:
                i = e["index"]
                if i <= len(self.log) - 1:
                    if self.log[i]["term"] != e["term"]:
                        # 冲突：截断自己的尾部。截掉的那些客户端的等待要立刻作废，
                        # 否则它们会一直等到超时，还可能被下一个占住同一下标的日志项误导。
                        for k in [k for k in self.waiters if k >= i]:
                            self.waiters.pop(k)["aborted"] = True
                        del self.log[i:]
                        rewritten = True
                    else:
                        continue                # 已有同一条，重复消息直接忽略
                self.log.append(e)
                if not rewritten:
                    self._append_wal(e)
            if rewritten:
                self._rewrite_wal()
            match = prev + len(entries)
            new_commit = min(msg["leader_commit"], len(self.log) - 1)
            if new_commit > self.commit_index:
                self.commit_index = new_commit
            self._apply_committed()
            return {"term": self.current_term, "success": True, "match_index": match}

    # ================= 运维接口 =================
    def status(self):
        with self.cv:
            return {
                "ok": True, "node": self.id, "state": self.state, "term": self.current_term,
                "leader": self.leader_id, "commit_index": self.commit_index,
                "last_applied": self.last_applied, "last_log_index": len(self.log) - 1,
                "log_len": len(self.log) - 1, "quorum": self.quorum_size(),
                "kv": {k: dict(v) for k, v in self.kv.items()},
                "dedup_size": len(self.dedup), "blocked": sorted(self.blocked),
                "delay_ms": self.delay_ms, "dup_extra": self.dup_extra,
                "clock_offset": self.clock_offset, "stale_read": self.allow_stale_read,
                "applied_total": self.applied_total, "reject_write": self.reject_write,
                "uptime": round(time.time() - self.started_at, 1),
                "fsync": self.fsync,
            }

    def admin(self, msg):
        cmd = msg.get("cmd")
        with self.cv:
            if cmd == "partition":
                self.blocked = set(msg.get("block", []))
            elif cmd == "heal":
                self.blocked = set()
            elif cmd == "delay":
                self.delay_ms = int(msg.get("ms", 0))
            elif cmd == "dup":
                self.dup_extra = int(msg.get("n", 0))
            elif cmd == "clock":
                self.clock_offset += int(msg.get("delta_ms", 0))
            elif cmd == "stale_read":
                self.allow_stale_read = bool(msg.get("on"))
            elif cmd == "cfg":
                if "quorum" in msg:
                    self.quorum_override = msg["quorum"]
                if "fsync" in msg:
                    self.fsync = bool(msg["fsync"])
            elif cmd == "clear_dedup":
                self.dedup.clear()
            else:
                return {"ok": False, "error": "unknown_admin"}
            return {"ok": True, "status": self.status()}

    # ================= 启动 =================
    def _serve(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Windows 上 SO_REUSEADDR 会允许两个进程绑同一端口（端口被"抢走"而不是报错），
        # 结果是新集群连到了上次没退干净的旧节点。这里改用独占绑定。
        if os.name == "nt":
            try:
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except (OSError, AttributeError):
                pass
        else:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind((self.bind, self.port))
        except OSError as ex:
            log_line("ERROR", "节点%d 绑定端口 %d 失败：%s —— 多半是上次的节点进程没退干净，"
                              "先把它结束掉再启动" % (self.id, self.port, ex))
            sys.exit(2)
        srv.listen(256)
        log_line("LISTEN", "节点%d 监听 %s:%d" % (self.id, self.bind, self.port))
        while not self.stopping:
            try:
                conn, _ = srv.accept()
            except OSError:
                break
            threading.Thread(target=self._serve_conn, args=(conn,), daemon=True).start()

    def _serve_conn(self, conn):
        try:
            conn.settimeout(5.0)
            f = conn.makefile("rb")
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                except Exception:
                    break
                # 故障注入：来自被隔离节点的消息直接不响应（等于网络断开）
                if msg.get("from") in self.blocked:
                    break
                resp = self.handle(msg)
                conn.sendall((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def start(self):
        threading.Thread(target=self._serve, daemon=True).start()
        threading.Thread(target=self._ticker, daemon=True).start()
        for p in self.peer_ids:
            threading.Thread(target=self._peer_loop, args=(p,), daemon=True).start()
        while True:
            time.sleep(3600)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--peers", required=True, help="形如 1@7001,2@7002,3@7003")
    ap.add_argument("--data", required=True)
    ap.add_argument("--bind", default="127.0.0.1", help="监听地址，容器里用 0.0.0.0")
    ap.add_argument("--quorum", type=int, default=0)
    ap.add_argument("--nosync", action="store_true")
    args = ap.parse_args()

    peer_map = {}
    for item in args.peers.split(","):
        nid, addr = item.split("@")
        if ":" in addr:                      # 形如 node2:7301
            host, p = addr.rsplit(":", 1)
        else:
            host, p = "127.0.0.1", addr
        peer_map[int(nid)] = (host, int(p))

    node = Node(args.id, args.port, peer_map, args.data,
                quorum=args.quorum or None, fsync=not args.nosync,
                bind=args.bind)
    node.start()


if __name__ == "__main__":
    main()
