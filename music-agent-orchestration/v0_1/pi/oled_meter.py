"""SH1106 playback UI: title + progress bar (percent-pos driven)."""

from __future__ import annotations

import logging
import math
import os

from PIL import Image, ImageDraw

from . import oled_status

log = logging.getLogger(__name__)


def _disabled() -> bool:
    v = os.environ.get("DISABLE_OLED", "").strip().lower()
    return v in ("1", "true", "yes")


def show_playback_bar(title: str, percent: float | None, tick: int = 0) -> None:
    """Line 1: truncated title. Block below: filled progress bar + tick pulse."""
    if _disabled():
        return
    dev = oled_status._get_device()
    if dev is None:
        return
    t = (title or "").strip() or "—"
    if len(t) > 21:
        t = t[:18] + "..."
    pct = 0.0 if percent is None or math.isnan(percent) else float(percent)
    pct = max(0.0, min(100.0, pct))
    w, h = dev.size
    img = Image.new("1", (w, h), 0)
    draw = ImageDraw.Draw(img)
    draw.text((0, 0), t[:21], fill=1)
    bar_y = 24
    bar_h = 12
    pad = 2
    inner_w = w - pad * 2
    filled = int(inner_w * (pct / 100.0))
    draw.rectangle([pad, bar_y, pad + inner_w, bar_y + bar_h], outline=1, fill=0)
    if filled > 0:
        draw.rectangle([pad, bar_y, pad + filled, bar_y + bar_h], outline=1, fill=1)
    pulse = (tick % 3) if pct > 0 else 0
    suffix = ("~" * pulse)[:3]
    pct_txt = f"{pct:4.0f}%{suffix}"[:16]
    draw.text((pad, bar_y + bar_h + 2), pct_txt, fill=1)
    try:
        dev.display(img)
    except Exception as e:
        log.warning("OLED meter display failed: %s", e)
