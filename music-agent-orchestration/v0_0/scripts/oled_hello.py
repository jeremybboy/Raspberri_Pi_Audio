#!/usr/bin/env python3
"""Short static OLED flash. For live feedback, use scripts/oled_live_status.py instead."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

os.environ.pop("DISABLE_OLED", None)

from pi import oled_status  # noqa: E402

if __name__ == "__main__":
    oled_status.show_status("Static hello", "oled_hello.py")
    time.sleep(5)
    print("Tip: run scripts/oled_live_status.py while uvicorn is up for dynamic /health.", flush=True)
