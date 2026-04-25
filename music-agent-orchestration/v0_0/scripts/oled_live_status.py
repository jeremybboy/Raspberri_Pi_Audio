#!/usr/bin/env python3
"""
Poll the v0_0 player /health and mirror state on the OLED (Ctrl+C to exit).

Run while uvicorn is up: line1 = hostname, line2 = OK + track count, or NO
SERVER if the HTTP endpoint is unreachable.
"""
from __future__ import annotations

import json
import os
import signal
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

os.environ.pop("DISABLE_OLED", None)

from pi import oled_status  # noqa: E402

_running = True


def _stop(*_args: object) -> None:
    global _running
    _running = False


def main() -> None:
    global _running
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    base = os.environ.get("PI_URL", "http://127.0.0.1:8765").rstrip("/")
    host = (socket.gethostname().strip() or "pi")[:21]
    interval = float(os.environ.get("OLED_POLL_SEC", "2"))

    while _running:
        line2 = "polling..."
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                n = int(data.get("track_count", 0))
                mf = bool(data.get("manifest_exists"))
                line2 = f"OK {n}tr mf={int(mf)}"[:16]
            else:
                line2 = "health !ok"[:16]
        except urllib.error.HTTPError:
            line2 = "HTTP ERR"[:16]
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            line2 = "NO SERVER"[:16]

        oled_status.show_status(host, line2)
        for _ in range(int(interval * 10)):
            if not _running:
                break
            time.sleep(0.1)

    oled_status.show_status(host, "live off")


if __name__ == "__main__":
    main()
