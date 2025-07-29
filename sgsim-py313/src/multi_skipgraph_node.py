#!/usr/bin/env python3
"""
Multi SkipGraph Node launcher (Windows friendly)
------------------------------------------------
* 1プロセスで複数ノード(HTTP+UDP広告)を立ち上げる。
* /shutdown で任意ノードを個別停止可
curl -X POST http://localhost:8002/shutdown　
* HTTP の / で key・mv・port・neighbors を JSON 返す（← port を追加）
"""

from __future__ import annotations
import socket, threading, time, random, json, queue, argparse
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Tuple

# ---------- default config ----------
LEVELS, ALPHA, MV_LEN = 10, 2, 32
UDP_PORT, BCAST_IP    = 12000, "255.255.255.255"
BCAST_INTERVAL_SEC, DUMP_INTERVAL_SEC = 2, 5
# ------------------------------------

ALL_NODES: Dict[Tuple[str, int], Dict[str, int | str]] = {}
_LOCK = threading.Lock()
STOP  = threading.Event()
_LOCAL_BUS: "queue.Queue[tuple[str,int,dict]]" = queue.Queue()
_MY_IP: str | None = None

FLAGS = {
    "enable_udp": True,
    "enable_fallback": True,
    "ignore_loopback": False,
    "quiet": False,
    "dump_interval": DUMP_INTERVAL_SEC,
}

# ---------- util ----------
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

def random_mv(length=MV_LEN, alpha=ALPHA):
    return "".join(str(random.randint(0, alpha - 1)) for _ in range(length))

def common_prefix(a: str, b: str):
    return sum(x == y for x, y in zip(a, b))

def on_discover(ip: str, port: int, info: dict):
    if FLAGS["ignore_loopback"] and ip.startswith("127."):
        return
    with _LOCK:
        first = (ip, port) not in ALL_NODES
        ALL_NODES[(ip, port)] = {"key": info["key"], "mv": info["mv"]}
    if first:
        log(f"[discovered] {ip}:{port} -> {info}")

# ---------- SkipNode ----------
@dataclass
class SkipNode:
    key: int
    mv: str
    port: int
    _httpd: HTTPServer = field(init=False, repr=False)

    # ---- neighbor calc ----
    def calc_neighbors(self):
        me = {"key": self.key, "mv": self.mv}
        with _LOCK:
            nodes = list(ALL_NODES.values()) + [me]

        nbs = []
        for lvl in range(LEVELS):
            same = [n for n in nodes if common_prefix(self.mv, n["mv"]) >= lvl + 1 and n["key"] != self.key]
            left  = max([n for n in same if n["key"] < self.key], default=None, key=lambda n: n["key"])
            right = min([n for n in same if n["key"] > self.key], default=None, key=lambda n: n["key"])
            nbs.append({
                "level": lvl,
                "LEFT" : [left["key"]]  if left  else [],
                "RIGHT": [right["key"]] if right else []
            })
        return nbs

    # ---- HTTP handler ----
    def _make_handler(self):
        node = self
        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/":
                    body = json.dumps({
                        "key"      : node.key,
                        "mv"       : node.mv,
                        "port"     : node.port,           # ★ 追加
                        "neighbors": node.calc_neighbors(),
                        "hop"      : 0
                    }).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)

            def do_POST(self):
                if self.path == "/shutdown":
                    self.send_response(200); self.end_headers()
                    self.wfile.write(b"BYE")
                    threading.Thread(target=node._httpd.shutdown, daemon=True).start()

            def log_message(self, *args, **kw):  # silence default logging
                return
        return H

    # ---- start services ----
    def start_http(self):
        self._httpd = HTTPServer(("", self.port), self._make_handler())
        threading.Thread(target=self._httpd.serve_forever, daemon=True,
                         name=f"HTTP-{self.port}").start()
        log(f"[HTTP] {get_my_ip()}:{self.port} (key={self.key})")

    def start_broadcast(self):
        if not FLAGS["enable_udp"] and not FLAGS["enable_fallback"]:
            return
        def loop():
            info = {"key": self.key, "mv": self.mv, "port": self.port}
            msg  = json.dumps(info).encode()
            if FLAGS["enable_udp"]:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                targets = [(BCAST_IP, UDP_PORT),
                           (get_my_ip(), UDP_PORT),
                           ("127.0.0.1", UDP_PORT)]
            while not STOP.is_set():
                if FLAGS["enable_udp"]:
                    for t in targets:
                        try: sock.sendto(msg, t)
                        except Exception: pass
                if FLAGS["enable_fallback"]:
                    _LOCAL_BUS.put((get_my_ip(), self.port, info))
                time.sleep(BCAST_INTERVAL_SEC)
        threading.Thread(target=loop, daemon=True,
                         name=f"BCAST-{self.port}").start()

# ---------- background listeners ----------
def start_udp_listener():
    if not FLAGS["enable_udp"]:
        return
    def loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", UDP_PORT))
            log(f"[UDP] listen 0.0.0.0:{UDP_PORT}")
        except OSError as e:
            log(f"[UDP] bind failed: {e}")
            return
        while not STOP.is_set():
            try:
                sock.settimeout(1.0)
                data, addr = sock.recvfrom(1024)
                info = json.loads(data.decode())
                on_discover(addr[0], info.get("port", 8000), info)
            except socket.timeout:
                continue
            except Exception:
                continue
    threading.Thread(target=loop, daemon=True, name="UDP-Listener").start()

def start_local_consumer():
    if not FLAGS["enable_fallback"]:
        return
    def loop():
        while not STOP.is_set():
            try:
                ip, port, info = _LOCAL_BUS.get(timeout=1.0)
                on_discover(ip, port, info)
            except queue.Empty:
                continue
    threading.Thread(target=loop, daemon=True, name="LOCALBUS").start()

def periodic_dump():
    if FLAGS["dump_interval"] <= 0:
        return
    while not STOP.is_set():
        time.sleep(FLAGS["dump_interval"])
        with _LOCK:
            d = {f"{ip}:{p}": v for (ip, p), v in ALL_NODES.items()}
        log(f"[DUMP] ALL_NODES({len(d)}): {d}")

# ---------- main ----------
def main(num=10, base_port=8000):
    log(f"Start {num} nodes on {get_my_ip()}")
    start_udp_listener()
    start_local_consumer()
    threading.Thread(target=periodic_dump, daemon=True).start()

    for i in range(num):
        port = base_port + i
        n = SkipNode(key=random.randint(100, 999), mv=random_mv(), port=port)
        n.start_http(); n.start_broadcast()

    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        STOP.set(); log("bye")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-n","--num", type=int, default=10)
    ap.add_argument("--base-port", type=int, default=8000)
    ap.add_argument("--bcast", default=BCAST_IP)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    BCAST_IP = args.bcast
    FLAGS["quiet"] = args.quiet
    main(args.num, args.base_port)
