#!/usr/bin/env python3
"""
Multi SkipGraph Node launcher (Windows friendly)
------------------------------------------------
* 1プロセスで複数ノード(HTTP+UDP広告)を立ち上げる。
* UDPブロードキャストが自分に返ってこない／フィルタされる環境でも動くよう、
  ローカルフォールバック(Queue経由で直接 on_discover に流す)を搭載。
* 可視化コードは変更しない前提なので、同一IP内の複数ノードは可視化側では
  1台として扱われる点だけ注意（必要なら可視化側を port もキーにする）。

CLI 例:
    python multi_skipgraph_node.py -n 50 --base-port 8000 --bcast 10.205.123.255

オプション:
    -n / --num            生成ノード数 (default 10)
    --base-port           最初のHTTPポート (default 8000)
    --bcast               UDP送信先ブロードキャストアドレス (default BCAST_IP)
    --dump                DUMP間隔秒。0で無効 (default 5)
    --no-fallback         ローカルフォールバック無効
    --no-udp              UDP受信・送信とも無効（フォールバックのみ）
    --ignore-loopback     127.* を on_discover で無視
    --quiet               ログ少なめ
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

# ========== default config ==========
LEVELS   = 10
ALPHA    = 2
MV_LEN   = 32

UDP_PORT = 12000
BCAST_IP = "255.255.255.255"   # 実ネットワークに合わせて上書き可能
BCAST_INTERVAL_SEC = 2
DUMP_INTERVAL_SEC  = 5
# ====================================

ALL_NODES: Dict[Tuple[str, int], Dict[str, int | str]] = {}
LOCAL_PORTS: set[int] = set()
_LOCK = threading.Lock()
STOP = threading.Event()
_MY_IP: str | None = None

# ローカルフォールバックバス（UDPが戻らない環境用）
LOCAL_BUS: "queue.Queue[tuple[str,int,dict]]" = queue.Queue()

# 実行時フラグ（CLIで切り替え）
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
        # 外部に接続せずともローカルNIC経由でIPが取れるトリック
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
    """UDP/フォールバック共通の発見処理"""
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
        me = {"key": self.key, "mv": self.mv}
        with _LOCK:
            all_nodes = list(ALL_NODES.values()) + [me]
        neighbors = []
        for level in range(LEVELS):
            same = [n for n in all_nodes if common_prefix(self.mv, n["mv"]) >= level + 1 and n["key"] != self.key]
            left  = max([n for n in same if n["key"] < self.key], default=None, key=lambda n: n["key"])
            right = min([n for n in same if n["key"] > self.key], default=None, key=lambda n: n["key"])
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
                    }).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
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
                # 念のため自分宛にも
                targets.append((get_my_ip(), UDP_PORT))
                targets.append(("127.0.0.1", UDP_PORT))
            else:
                sock = None  # type: ignore
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


def main(num_nodes: int = 10, base_port: int = 8000):
    my_ip = get_my_ip()
    log(f"Start {num_nodes} nodes on {my_ip}")
    log(f"BCAST_IP={BCAST_IP}, UDP_PORT={UDP_PORT}")

    start_udp_listener()
    start_local_bus_consumer()
    threading.Thread(target=periodic_dump, daemon=True, name="DUMPER").start()

    for i in range(num_nodes):
        port = base_port + i
        LOCAL_PORTS.add(port)
        n = SkipNode(key=random.randint(100, 999), mv=random_mv(), port=port)
        n.start_http()
        n.start_broadcast()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        STOP.set()
        log("bye")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--num", type=int, default=10000, help="number of nodes")
    parser.add_argument("--base-port", type=int, default=8000)
    parser.add_argument("--bcast", default=BCAST_IP, help="broadcast address")
    parser.add_argument("--dump", type=int, default=DUMP_INTERVAL_SEC, help="dump interval sec (0=off)")
    parser.add_argument("--no-fallback", action="store_true")
    parser.add_argument("--no-udp", action="store_true")
    parser.add_argument("--ignore-loopback", action="store_true")
    parser.add_argument("--quiet", action="store_true")

    args = parser.parse_args()

    BCAST_IP = args.bcast
    FLAGS["enable_udp"]      = not args.no_udp
    FLAGS["enable_fallback"] = not args.no_fallback
    FLAGS["ignore_loopback"] = args.ignore_loopback
    FLAGS["quiet"]           = args.quiet
    FLAGS["dump_interval"]   = args.dump

    main(num_nodes=args.num, base_port=args.base_port)
