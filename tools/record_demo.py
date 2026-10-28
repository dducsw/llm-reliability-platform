"""Chạy scenario chính ở chế độ quay video (bật chế độ che key trên Console).

1. (tuỳ chọn) `demo_reset --yes` để bắt đầu từ trạng thái sạch.
2. Mở Console với `?present=1`: chữ to, narration ribbon, demo clock, che chuỗi giống secret.
3. Chạy `reflex-sim run <scenario>` (mặc định silent-brownout, `--fast` = ×60).

    uv run python tools/record_demo.py                       # silent-brownout --fast
    uv run python tools/record_demo.py --scenario 429-storm --realtime --reset
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--scenario", default="silent-brownout")
    ap.add_argument("--realtime", action="store_true", help="không dùng --fast (×1)")
    ap.add_argument("--reset", action="store_true", help="demo_reset --yes trước khi chạy")
    ap.add_argument("--console", default="http://localhost:5173")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--lead-in", type=float, default=5.0, help="giây chờ trước khi bơm lỗi")
    args = ap.parse_args()

    if not (Path("scenarios") / f"{args.scenario}.yaml").exists():
        sys.exit(f"Không có scenario {args.scenario} trong scenarios/")
    if args.reset:
        subprocess.run([sys.executable, "tools/demo_reset.py", "--yes"], check=True)

    url = f"{args.console}/?present=1"
    print(f"Console (present mode): {url}")
    if not args.no_browser:
        webbrowser.open(url)
    time.sleep(args.lead_in)  # để người quay kịp bấm record

    cmd = ["reflex-sim", "run", args.scenario, *([] if args.realtime else ["--fast"])]
    print("$", " ".join(cmd))
    sys.exit(subprocess.run(["uv", "run", *cmd]).returncode)


if __name__ == "__main__":
    main()
