"""SH1106 OLED: track title + PLAYING / STOPPED for v0_2 player."""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

_device = None
_oled_init_failed = False


def _disabled() -> bool:
    v = os.environ.get("DISABLE_OLED", "").strip().lower()
    return v in ("1", "true", "yes")


def _get_device():
    global _device, _oled_init_failed
    if _disabled():
        return None
    if _oled_init_failed:
        return None
    if _device is not None:
        return _device
    try:
        from luma.core.interface.serial import i2c
        from luma.oled.device import sh1106
    except ImportError as e:
        log.warning("OLED libraries unavailable: %s", e)
        _oled_init_failed = True
        return None
    port = int(os.environ.get("I2C_PORT", "1"))
    addr_s = os.environ.get("I2C_ADDR", "0x3C").strip()
    addr = int(addr_s, 16) if addr_s.lower().startswith("0x") else int(addr_s, 10)
    try:
        serial = i2c(port=port, address=addr)
        _device = sh1106(serial)
    except Exception as e:
        log.warning("OLED init failed (playback still works): %s", e)
        _oled_init_failed = True
        return None
    return _device


def show_status(title: str, state: str) -> None:
    """Draw title (line 1) and state PLAYING or STOPPED (line 2)."""
    from PIL import Image, ImageDraw

    dev = _get_device()
    if dev is None:
        return
    t = (title or "").strip() or "—"
    if len(t) > 21:
        t = t[:18] + "..."
    s = (state or "").strip()[:16] or "—"
    w, h = dev.size
    img = Image.new("1", (w, h), 0)
    draw = ImageDraw.Draw(img)
    draw.text((0, 0), t[:21], fill=1)
    draw.text((0, 24), s, fill=1)
    try:
        dev.display(img)
    except Exception as e:
        log.warning("OLED display failed: %s", e)
