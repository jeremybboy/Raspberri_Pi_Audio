"""SH1106 playback UI: title + clock + VU-style meter."""

from __future__ import annotations

import logging
import math
import os
import re
import subprocess

from PIL import Image, ImageDraw

from . import oled_status

log = logging.getLogger(__name__)


def _disabled() -> bool:
    v = os.environ.get("DISABLE_OLED", "").strip().lower()
    return v in ("1", "true", "yes")


def _fmt_mmss(seconds: float | None) -> str:
    if seconds is None or math.isnan(seconds) or seconds < 0:
        return "--:--"
    sec = int(seconds)
    m, s = divmod(sec, 60)
    return f"{m:02d}:{s:02d}"


def _db_to_fill(db: float) -> float:
    # Map [-60 dB, 0 dB] to [0, 1]
    if db <= -60.0:
        return 0.0
    if db >= 0.0:
        return 1.0
    return (db + 60.0) / 60.0


def estimate_db_window(path: str, time_pos: float | None, window_s: float = 0.12) -> float | None:
    """Estimate RMS dB around current playback time with ffmpeg astats."""
    if time_pos is None or time_pos < 0:
        return None
    start = max(0.0, float(time_pos) - (window_s / 2.0))
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-v",
        "info",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{window_s:.3f}",
        "-i",
        path,
        "-af",
        "astats=metadata=1:reset=1",
        "-f",
        "null",
        "-",
    ]
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=0.8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = p.stderr or ""
    m = re.search(r"RMS level dB:\s*(-?\d+(?:\.\d+)?)", text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def show_playback_vu(
    title: str,
    time_pos: float | None,
    duration: float | None,
    db_value: float | None,
    tick: int = 0,
) -> None:
    """Line 1: title. Line 2: mm:ss / mm:ss. Bottom: VU-style bar."""
    if _disabled():
        return
    dev = oled_status._get_device()
    if dev is None:
        return
    t = (title or "").strip() or "—"
    if len(t) > 21:
        t = t[:18] + "..."
    w, h = dev.size
    img = Image.new("1", (w, h), 0)
    draw = ImageDraw.Draw(img)
    draw.text((0, 0), t[:21], fill=1)

    clock_txt = f"{_fmt_mmss(time_pos)} / {_fmt_mmss(duration)}"[:21]
    draw.text((0, 12), clock_txt, fill=1)

    bar_y = 27
    bar_h = 10
    pad = 2
    inner_w = w - pad * 2

    # If we don't have dB yet, keep a subtle idle pulse.
    if db_value is None or math.isnan(db_value):
        fill_ratio = ((tick % 6) + 1) / 12.0
        meter_txt = "VU -- dB"
    else:
        fill_ratio = _db_to_fill(float(db_value))
        meter_txt = f"VU {db_value:5.1f} dB"[:16]
    filled = int(inner_w * max(0.0, min(1.0, fill_ratio)))

    draw.rectangle([pad, bar_y, pad + inner_w, bar_y + bar_h], outline=1, fill=0)
    if filled > 0:
        draw.rectangle([pad, bar_y, pad + filled, bar_y + bar_h], outline=1, fill=1)
    draw.text((pad, bar_y + bar_h + 1), meter_txt, fill=1)
    try:
        dev.display(img)
    except Exception as e:
        log.warning("OLED meter display failed: %s", e)
