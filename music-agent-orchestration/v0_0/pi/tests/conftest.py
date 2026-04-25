"""Pytest: v0_0 on path, OLED off for headless runs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DISABLE_OLED", "1")

_root = Path(__file__).resolve().parents[2]  # .../music-agent-orchestration/v0_0
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
