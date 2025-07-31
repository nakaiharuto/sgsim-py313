#!/usr/bin/env python3
"""
Multi SkipGraph Node launcher (Windows friendly)
------------------------------------------------
* 1プロセスで複数ノード(HTTP+UDP広告)を立ち上げる
* /shutdown で任意ノードを個別停止可 (curl -X POST http://localhost:8002/shutdown)
* HTTP / で key・mv・port・neighbors を JSON返す（portを追加）
* CLIで n押下→key/mv/port対話式入力（Enterで自動割当、重複安全）/ lで現ノード一覧
* Ctrl+Cで中断OK

[NEW] 各レベルのneighbor探索で端（min/max key）同士も必ずneighborとして接続（リング状の連結）。
ノードの状態はnodes.jsonに常に保存し、どのノードのneighbor計算でも共通データを利用。

サーバー起動例:
    python multi_skipgraph_node.py -n 5 --base-port 8000

CLI例:
    python multi_skipgraph_node.py -n 5 --base-port 8000 --bcast 10.205.123.255
"""

from __future__ import annotations
import socket
import threading
import time
import random
import json
import queue
import argparse
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Tuple

LEVELS   = 10
ALPHA    = 2
MV_LEN   = 32

UDP_PORT = 12000
BCAST_IP = "255.255.255.255"
BCAST_INTERVAL_SEC = 2
DUMP_INTERVAL_SEC  = 5

ALL_NODES: Dict[Tuple[str, int], Dict[str, int | str]] = {}
LOCAL_PORTS: set[int] = set()
_LOCK = threading.Lock()
STOP = threading.Event()
_MY_IP: str | None = None

LOCAL_BUS: "queue.Queue[tuple[str,int,dict]]" = queue.Queue()
NODES_LIST = []

NODES_FILE = "nodes.json"  # <--- ここでノードリスト保存！

def save_nodes_to_file():
    with _LOCK:
        nodes = [{"key": n.key, "mv": n.mv, "port": n.port} for n in NODES_LIST]
    with open(NODES_FILE, "w", encoding="utf-8") as f:
        json.dump(nodes, f, ensure_ascii=False, indent=2)

def load_nodes_from_file():
    try:
        with open(NODES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

FLAGS = {
    "enable_udp": True,
    "enable_fallback": True,
    "ignore_loopback": False,
    "quiet": False,
    "dump_interval": DUMP_INTERVAL_SEC,
}

def log(msg: str):
    if not FLAGS["quiet"]:
        print(msg)

def get_my_ip() -> str:
    global _MY_IP
    if _MY_IP:
        return _MY_IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        _MY_IP = s.getsockname()[0]
    except Exception:
        _MY_IP = "127.0.0.1"
    finally:
        s.close()
    return _MY_IP

def random_mv(length: int = MV_LEN, alpha: int = ALPHA) -> str:
    return "".join(str(random.randint(0, alpha - 1)) for _ in range(length))

def common_prefix(a: str, b: str) -> int:
    return sum(x == y for x, y in zip(a, b))

def on_discover(ip: str, port: int, info: dict):
    if FLAGS["ignore_loopback"] and ip.startswith("127."):
        return
    with _LOCK:
        first = (ip, port) not in ALL_NODES
        ALL_NODES[(ip, port)] = {"key": info["key"], "mv": info["mv"]}
    if first:
        log(f"[discovered] {ip}:{port} -> {info}")

@dataclass
class SkipNode:
    key: int
    mv: str
    port: int
    _httpd: HTTPServer = field(init=False, repr=False)

    def calc_neighbors(self):
        me = {"key": self.key, "mv": self.mv, "port": self.port}
        all_nodes = load_nodes_from_file() + [me]
        keys_sorted = sorted(n["key"] for n in all_nodes)
        neighbors = []
        for level in range(LEVELS):
            same = [n for n in all_nodes if common_prefix(self.mv, n["mv"]) >= level + 1 and n["key"] != self.key]
            if not same:
                neighbors.append({
                    "level": level,
                    "LEFT": [],
                    "RIGHT": []
                })
                continue

            lefts = [n for n in same if n['key'] < self.key]
            rights = [n for n in same if n['key'] > self.key]

            # ---- リングneighbor実装 ----
            left = max(lefts, key=lambda n: n['key']) if lefts else (
                max(same, key=lambda n: n['key']) if same else None
            )
            right = min(rights, key=lambda n: n['key']) if rights else (
                min(same, key=lambda n: n['key']) if same else None
            )
            neighbors.append({
                "level": level,
                "LEFT":  [left["key"]]  if left  else [],
                "RIGHT": [right["key"]] if right else []
            })
        return neighbors

    def _make_handler(self):
        node = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/":
                    body = json.dumps({
                        "key": node.key,
                        "mv": node.mv,
                        "neighbors": node.calc_neighbors(),
                        "port": node.port,
                        "hop": 0
                    }).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    try:
                        self.wfile.write(body)
                    except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
                        pass

            def do_POST(self):
                if self.path == "/shutdown":
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"BYE")
                    threading.Thread(target=node._httpd.shutdown, daemon=True).start()
                    with _LOCK:
                        NODES_LIST[:] = [n for n in NODES_LIST if n.port != node.port]
                        ALL_NODES.pop((get_my_ip(), node.port), None)
                    save_nodes_to_file()

            def log_message(self, *args, **kwargs):
                return
        return Handler

    def start_http(self):
        self._httpd = HTTPServer(("", self.port), self._make_handler())
        threading.Thread(target=self._httpd.serve_forever,
                         daemon=True,
                         name=f"HTTP-{self.port}").start()
        log(f"[HTTP] {get_my_ip()}:{self.port} (key={self.key})")

    def start_broadcast(self):
        if not FLAGS["enable_udp"] and not FLAGS["enable_fallback"]:
            return
        def broadcaster():
            info = {"key": self.key, "mv": self.mv, "port": self.port}
            msg  = json.dumps(info).encode()
            targets = []
            if FLAGS["enable_udp"]:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                targets.append((BCAST_IP, UDP_PORT))
                targets.append((get_my_ip(), UDP_PORT))
                targets.append(("127.0.0.1", UDP_PORT))
            else:
                sock = None
            while not STOP.is_set():
                if FLAGS["enable_udp"]:
                    for t in targets:
                        try:
                            sock.sendto(msg, t)
                        except Exception:
                            pass
                if FLAGS["enable_fallback"]:
                    LOCAL_BUS.put((get_my_ip(), self.port, info))
                time.sleep(BCAST_INTERVAL_SEC)
        threading.Thread(target=broadcaster, daemon=True, name=f"BCAST-{self.port}").start()

def start_udp_listener():
    if not FLAGS["enable_udp"]:
        return
    def listener():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", UDP_PORT))
            log(f"[UDP] listening on 0.0.0.0:{UDP_PORT}")
        except OSError as e:
            log(f"[UDP] bind failed: {e}  -> UDP受信は諦め")
            return
        while not STOP.is_set():
            try:
                sock.settimeout(1.0)
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            except Exception:
                continue
            try:
                info = json.loads(data.decode())
                ip   = addr[0]
                port = info.get("port", 8000)
                on_discover(ip, port, info)
            except Exception:
                pass
    threading.Thread(target=listener, daemon=True, name="UDP-Listener").start()

def start_local_bus_consumer():
    if not FLAGS["enable_fallback"]:
        return
    def consumer():
        while not STOP.is_set():
            try:
                ip, port, info = LOCAL_BUS.get(timeout=1.0)
            except queue.Empty:
                continue
            on_discover(ip, port, info)
    threading.Thread(target=consumer, daemon=True, name="LOCALBUS").start()

def periodic_dump():
    if FLAGS["dump_interval"] <= 0:
        return
    while not STOP.is_set():
        time.sleep(FLAGS["dump_interval"])
        with _LOCK:
            dump = {f"{ip}:{p}": v for (ip, p), v in ALL_NODES.items()}
        log(f"[DUMP] ALL_NODES({len(dump)}): {dump}")

# ----- 新規ノード追加CLI -----
def next_free_port(base, used_ports):
    p = base
    while p in used_ports:
        p += 1
    return p

def next_free_key(used_keys):
    while True:
        k = random.randint(100, 999)
        if k not in used_keys:
            return k

def node_adder_cli(base_port):
    while not STOP.is_set():
        try:
            cmd = input("新ノード追加[n] / 現在ノード一覧[l] または Enterで待機: ").strip()
            if cmd == "l":
                with _LOCK:
                    print("[現状ノード一覧]")
                    for nn in NODES_LIST:
                        print(f"  key={nn.key}, port={nn.port}")
                print()
                continue
            if cmd != "n":
                continue
            print("\n[ノード追加] key を入力してください（Enterでランダム）: ", end="")
            key_in = input().strip()
            with _LOCK:
                existing_keys = {n.key for n in NODES_LIST}
            if key_in:
                try:
                    key = int(key_in)
                    if key in existing_keys:
                        print("[エラー] そのkeyは既に使われています")
                        continue
                except:
                    print("[エラー] 整数で入力してください")
                    continue
            else:
                key = next_free_key(existing_keys)

            print("[ノード追加] mv（MembershipVector）を入力してください（Enterでランダム）: ", end="")
            mv_in = input().strip()
            mv = mv_in if mv_in else random_mv()

            with _LOCK:
                used_ports = {n.port for n in NODES_LIST}
            suggested_port = next_free_port(base_port, used_ports)
            print(f"[ノード追加] port を入力してください（Enterで自動採番: {suggested_port}) : ", end="")
            port_in = input().strip()
            if port_in:
                try:
                    port = int(port_in)
                    if port in used_ports:
                        print("[エラー] そのportは既に使われています")
                        continue
                except:
                    print("[エラー] 整数で入力してください")
                    continue
            else:
                port = suggested_port

            n = SkipNode(key=key, mv=mv, port=port)
            n.start_http()
            n.start_broadcast()
            with _LOCK:
                NODES_LIST.append(n)
            save_nodes_to_file()
            print(f"[OK] 新ノード追加: key={key}, mv={mv}, port={port}\n")

            print("[現状ノード一覧]")
            with _LOCK:
                for nn in NODES_LIST:
                    print(f"  key={nn.key}, port={nn.port}")
            print()
        except KeyboardInterrupt:
            print("\n[中断] ノード追加をキャンセルしました\n")
            continue

def main(num_nodes: int = 10, base_port: int = 8000):
    my_ip = get_my_ip()
    log(f"Start {num_nodes} nodes on {my_ip}")
    log(f"BCAST_IP={BCAST_IP}, UDP_PORT={UDP_PORT}")

    start_udp_listener()
    start_local_bus_consumer()
    threading.Thread(target=periodic_dump, daemon=True, name="DUMPER").start()
    threading.Thread(target=node_adder_cli, args=(base_port,), daemon=True).start()

    with _LOCK:
        for i in range(num_nodes):
            port = base_port + i
            LOCAL_PORTS.add(port)
            n = SkipNode(key=next_free_key({n.key for n in NODES_LIST}),
                         mv=random_mv(), port=port)
            n.start_http()
            n.start_broadcast()
            NODES_LIST.append(n)
    save_nodes_to_file()  # <--- 最初の状態も保存！

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        STOP.set()
        log("bye")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--num", type=int, default=10, help="number of nodes")
    parser.add_argument("--base-port", type=int, default=8000)
    parser.add_argument("--bcast", default=BCAST_IP, help="broadcast address")
    parser.add_argument("--dump", type=int, default=DUMP_INTERVAL_SEC, help="dump interval sec (0=off)")
    parser.add_argument("--no-fallback", action="store_true")
    parser.add_argument("--no-udp", action="store_true")
    parser.add_argument("--ignore-loopback", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="ログを表示する")

    args = parser.parse_args()

    BCAST_IP = args.bcast
    FLAGS["enable_udp"]      = not args.no_udp
    FLAGS["enable_fallback"] = not args.no_fallback
    FLAGS["ignore_loopback"] = args.ignore_loopback
    FLAGS["quiet"]           = not args.verbose
    FLAGS["dump_interval"]   = args.dump

    main(num_nodes=args.num, base_port=args.base_port)
