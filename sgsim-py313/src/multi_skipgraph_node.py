#!/usr/bin/env python3
"""
Multi SkipGraph Node launcher (cross-host + Windows friendly)
------------------------------------------------------------
* 1プロセスで複数ノード(HTTP+UDP広告)を立ち上げる
* /shutdown で任意ノードを個別停止可 (curl -X POST http://<host>:<port>/shutdown)
* HTTP / で key・mv・port・neighbors を JSON返す
* CLIで n押下→key/mv/port対話式入力（Enterで自動割当、重複安全）/ lで現ノード一覧
* Ctrl+Cで中断OK

[FIX]
- 近傍計算(calc_neighbors)が他ホストのノードを参照しない不具合を修正
  -> ALL_NODES(発見済み) + NODES_LIST(ローカル) + nodes.json(参考) をマージして重複排除
- 発見(on_discover)時にオプションで nodes.json へも反映
- ブロードキャストが落とされる環境向けに --peers でユニキャスト先を追加
- ログ/挙動を --verbose, --quiet で制御

起動例:
  python multi_skipgraph_node_fixed.py -n 3 --base-port 8000 --bcast 10.205.127.255 --verbose
  python multi_skipgraph_node_fixed.py -n 3 --base-port 8000 --peers 10.205.109.98,10.205.120.106 --no-udp --verbose
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
from typing import Dict, Tuple, List

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
NODES_LIST: List["SkipNode"] = []

NODES_FILE = "nodes.json"  # 共有/参考用

FLAGS = {
    "enable_udp": True,
    "enable_fallback": True,
    "ignore_loopback": False,
    "quiet": False,
    "dump_interval": DUMP_INTERVAL_SEC,
    "persist_on_discover": True,  # 発見時にnodes.jsonへも保存
}

CLI_PEERS: List[str] = []  # ユニキャスト先(IPv4文字列)


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


def save_nodes_to_file():
    """ローカルノードに加え、発見済みも含めて保存(重複排除)。"""
    try:
        with _LOCK:
            locals_ = [{"key": n.key, "mv": n.mv, "port": n.port} for n in NODES_LIST]
            discovered = [{"key": v["key"], "mv": v["mv"], "port": p}
                          for (ip, p), v in ALL_NODES.items()]
        seen = set()
        merged = []
        for n in locals_ + discovered:
            kp = (n["key"], n["port"])
            if kp in seen:
                continue
            seen.add(kp)
            merged.append(n)
        with open(NODES_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"[WARN] save_nodes_to_file failed: {e}")


def load_nodes_from_file():
    try:
        with open(NODES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def on_discover(ip: str, port: int, info: dict):
    if FLAGS["ignore_loopback"] and ip.startswith("127."):
        return
    with _LOCK:
        first = (ip, port) not in ALL_NODES
        ALL_NODES[(ip, port)] = {"key": info.get("key"), "mv": info.get("mv")}
    if first:
        log(f"[discovered] {ip}:{port} -> key={info.get('key')} mv={info.get('mv')}")
        if FLAGS["persist_on_discover"]:
            save_nodes_to_file()


@dataclass
class SkipNode:
    key: int
    mv: str
    port: int
    _httpd: HTTPServer = field(init=False, repr=False)

    def calc_neighbors(self):
        me = {"key": self.key, "mv": self.mv, "port": self.port}

        with _LOCK:
            discovered = [{"key": v["key"], "mv": v["mv"], "port": p}
                          for (ip, p), v in ALL_NODES.items()]
            locals_ = [{"key": n.key, "mv": n.mv, "port": n.port}
                       for n in NODES_LIST]
        file_nodes = load_nodes_from_file()

        # 重複排除
        seen = set()
        all_nodes = []
        for n in file_nodes + locals_ + discovered + [me]:
            try:
                kp = (int(n["key"]), int(n["port"]))
            except Exception:
                # 変なデータが混じってもスキップ
                continue
            if kp in seen:
                continue
            seen.add(kp)
            all_nodes.append({"key": int(n["key"]), "mv": str(n["mv"]), "port": int(n["port"])})

        neighbors = []
        for level in range(LEVELS):
            same = [n for n in all_nodes if n["key"] != self.key and common_prefix(self.mv, n["mv"]) >= level + 1]
            if not same:
                neighbors.append({"level": level, "LEFT": [], "RIGHT": []})
                continue

            lefts  = [n for n in same if n['key'] < self.key]
            rights = [n for n in same if n['key'] > self.key]

            left = max(lefts,  key=lambda n: n['key']) if lefts else (max(same, key=lambda n: n['key']) if same else None)
            right = min(rights, key=lambda n: n['key']) if rights else (min(same, key=lambda n: n['key']) if same else None)

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
                        "host": get_my_ip(),
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
                    try:
                        self.wfile.write(b"BYE")
                    except Exception:
                        pass
                    threading.Thread(target=node._httpd.shutdown, daemon=True).start()
                    with _LOCK:
                        try:
                            NODES_LIST[:] = [n for n in NODES_LIST if n.port != node.port]
                            ALL_NODES.pop((get_my_ip(), node.port), None)
                        except Exception:
                            pass
                    save_nodes_to_file()

            def log_message(self, *args, **kwargs):
                return
        return Handler

    def start_http(self):
        # 全IFで待受 (FWに注意)
        self._httpd = HTTPServer(("", self.port), self._make_handler())
        threading.Thread(target=self._httpd.serve_forever,
                         daemon=True,
                         name=f"HTTP-{self.port}").start()
        log(f"[HTTP] {get_my_ip()}:{self.port} (key={self.key})")

    def start_broadcast(self):
        if not FLAGS["enable_udp"] and not FLAGS["enable_fallback"] and not CLI_PEERS:
            return

        def broadcaster():
            info = {"key": self.key, "mv": self.mv, "port": self.port}
            msg  = json.dumps(info).encode()

            sock = None
            if FLAGS["enable_udp"]:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            while not STOP.is_set():
                # UDPブロードキャスト/ユニキャスト
                if FLAGS["enable_udp"] and sock:
                    targets = [(BCAST_IP, UDP_PORT), (get_my_ip(), UDP_PORT), ("127.0.0.1", UDP_PORT)]
                    for peer in CLI_PEERS:
                        targets.append((peer, UDP_PORT))
                    for t in targets:
                        try:
                            sock.sendto(msg, t)
                        except Exception:
                            pass
                # ローカルフォールバック
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
                info = json.loads(data.decode(errors="ignore"))
                ip   = addr[0]
                port = int(info.get("port", 8000))
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
    log(f"BCAST_IP={BCAST_IP}, UDP_PORT={UDP_PORT}, peers={CLI_PEERS}")

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
    save_nodes_to_file()  # 初期状態も保存

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
    parser.add_argument("--peers", type=str, default="", help="カンマ区切りのユニキャスト送信先IPv4(例: 10.205.109.98,10.205.120.106)")
    parser.add_argument("--no-persist-discover", action="store_true", help="発見時にnodes.jsonへ保存しない")

    args = parser.parse_args()

    # 反映
    BCAST_IP = args.bcast
    FLAGS["enable_udp"]      = not args.no_udp
    FLAGS["enable_fallback"] = not args.no_fallback
    FLAGS["ignore_loopback"] = args.ignore_loopback
    FLAGS["quiet"]           = not args.verbose
    FLAGS["dump_interval"]   = args.dump
    FLAGS["persist_on_discover"] = not args.no_persist_discover

    if args.peers:
        CLI_PEERS[:] = [p.strip() for p in args.peers.split(',') if p.strip()]

    main(num_nodes=args.num, base_port=args.base_port)
