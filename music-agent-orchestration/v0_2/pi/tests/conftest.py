"""Pytest: v0_2 on path, OLED and playback meter off for headless runs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DISABLE_OLED", "1")
os.environ.setdefault("DISABLE_PLAYBACK_METER", "1")

_root = Path(__file__).resolve().parents[2]  # .../music-agent-orchestration/v0_2
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
