#!/usr/bin/env python
# run_all.py  v2  ―  失敗ジョブだけ再挑戦出来る簡易ランチャ
#   python run_all.py            … 全ケース実行（PNG 出力のみ）
#   python run_all.py --retry    … 失敗したものだけ再実行（GUI OK）

import os, sys, subprocess, tempfile, json
from pathlib import Path
from argparse import ArgumentParser

print("=== run_all.py start ===", flush=True)
print("=== CWD:", os.getcwd(), flush=True)
print("=== argv:", sys.argv, flush=True)
print("=== executable:", sys.executable, flush=True)

PY      = Path(sys.executable)
SG_MAIN = Path(__file__).with_name("sg_main.py")
FAILLOG = Path("failed.txt")             # ← 失敗コマンドを一行 JSON で保存

BATCH_CMDS = [
    ("basic",          "-n 8"),
    ("basic",          "-n 32 --output-topology-max-level 3"),
    ("unicast",        "-n 32 --unicast-algorithm greedy"),
    ("unicast",        "-n 32 --unicast-algorithm original"),
    ("unicast",        "-n 32 --unicast-algorithm greedy --output-hop-graph --diagonal"),
    ("unicast_vary_n", ""),
]

def build_cmd(exp: str, extra: str, *, interactive=False):
    base = [str(PY), str(SG_MAIN), "--exp", exp, "--fast-join"]
    if interactive:
        base.append("--interactive")
    base.extend(extra.split())
    return base

def run(cmd: list[str], workdir: Path, env) -> bool:
    print("> Running:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=workdir, env=env)
    return res.returncode == 0

def main():
    parser = ArgumentParser()
    parser.add_argument("--retry", action="store_true",
                        help="failed.txt を読んで失敗ケースだけ実行")
    args = parser.parse_args()

    if args.retry and not FAILLOG.exists():
        sys.exit("[ERROR] 失敗ログが無いので --retry は使えません")

    # ------------------------------------------------------------------
    if not args.retry:
        # 一時ディレクトリで PNG 生成だけ
        with tempfile.TemporaryDirectory(prefix="sgsim_case", suffix=".tmp") as tmpdir:
            tmp = Path(tmpdir)
            env = {**os.environ, "MPLBACKEND": "Agg"}

            failed = []
            for exp, extra in BATCH_CMDS:
                cmd = build_cmd(exp, extra)
                ok = run(cmd, tmp, env)
                if not ok:
                    failed.append({"exp": exp, "extra": extra})

            # 失敗をログに保存
            if failed:
                FAILLOG.write_text("\n".join(json.dumps(x) for x in failed), encoding="utf-8")
                print("[WARN] {} 件失敗 → {} に保存".format(len(failed), FAILLOG))
                sys.exit(1)

        print("[OK] バッチは全成功！GUI 付き for n=8 だけ実行します")

        # GUI 表示は作業ディレクトリで
        gui_cmd = build_cmd("basic", "-n 8", interactive=True)
        run(gui_cmd, Path.cwd(), os.environ)
        print("[OK] ALL DONE")
        FAILLOG.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    else:
        failed_cases = [json.loads(l) for l in FAILLOG.read_text().splitlines()]
        still_failed  = []

        for case in failed_cases:
            cmd = build_cmd(case["exp"], case["extra"], interactive=True)
            ok = run(cmd, Path.cwd(), os.environ)
            if not ok:
                still_failed.append(case)

        if still_failed:
            FAILLOG.write_text("\n".join(json.dumps(x) for x in still_failed), encoding="utf-8")
            print("[WARN] まだ {} 件失敗… 詳細は {}".format(len(still_failed), FAILLOG))
            sys.exit(1)

        print("[OK] 再実行分も全部 OK！")
        FAILLOG.unlink(missing_ok=True)

# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()
