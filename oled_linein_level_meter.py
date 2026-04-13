#!/usr/bin/env python3
"""
SH1106 OLED level meter for USB line-in (e.g. Behringer UCA202).
Shows mono VU bar + L/R mini meters + RMS/peak text so you can see how much
signal is reaching the Pi. Ctrl+C to exit.
"""
from __future__ import annotations

import signal
import sys
import threading
import time

import numpy as np
import sounddevice as sd

from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from PIL import Image, ImageDraw

# ---------- CONFIG ----------
DEVICE_MATCH = ["USB Audio CODEC"]
I2C_ADDR = 0x3C
BLOCK = 1024

DISPLAY_FPS = 22.0

# Below this mono RMS, show "NO SIGNAL" (tweak if noisy room)
NO_SIGNAL_RMS = 0.0025

# Mono RMS that maps to a full-width bar (float32 nominal +/-1.0)
METER_REF_RMS = 0.06

# Peak ballistics (per display frame, ~1/DISPLAY_FPS)
PEAK_DECAY = 0.88
RMS_SMOOTH = 0.35
# ---------------------------

running = True
_lock = threading.Lock()
_rms_mono = 0.0
_peak_mono = 0.0
_rms_l = 0.0
_rms_r = 0.0
_hold_frac = 0.0
_disp_rms = 0.0


def pick_input_device() -> tuple[int, str]:
    devs = sd.query_devices()
    for i, d in enumerate(devs):
        if d.get("max_input_channels", 0) <= 0:
            continue
        name = d.get("name", "")
        if any(m.lower() in name.lower() for m in DEVICE_MATCH):
            return i, name
    raise RuntimeError("USB Audio CODEC not found among input devices")


def pick_samplerate(device_index: int) -> int:
    info = sd.query_devices(device_index, "input")
    sr = info.get("default_samplerate")
    if sr is not None:
        return int(round(float(sr)))
    return 48000


def _cb(indata, frames, time_info, status):
    global _rms_mono, _peak_mono, _rms_l, _rms_r
    l_ = indata[:, 0].astype(np.float32)
    r_ = indata[:, 1].astype(np.float32)
    mono = 0.5 * (l_ + r_)
    with _lock:
        _rms_l = float(np.sqrt(np.mean(l_ * l_)))
        _rms_r = float(np.sqrt(np.mean(r_ * r_)))
        _rms_mono = float(np.sqrt(np.mean(mono * mono)))
        _peak_mono = float(np.max(np.abs(mono)))


def handle_signal(signum, frame):
    global running
    running = False


def _level_frac(rms: float, peak: float) -> float:
    """Map RMS/peak to 0..1 for bar width."""
    a = rms / max(METER_REF_RMS, 1e-9)
    b = (peak * 0.9) / max(METER_REF_RMS * 2.2, 1e-9)
    return float(min(1.0, max(a, b)))


def draw_meter(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    frac: float,
    hold_frac: float,
    rms_m: float,
    pk: float,
    rms_l: float,
    rms_r: float,
    no_signal: bool,
) -> None:
    draw.rectangle((0, 0, w - 1, h - 1), outline=0, fill=0)
    draw.text((0, 0), "LINE IN", fill=1)

    x0, x1 = 4, w - 5
    mw = x1 - x0 + 1
    y_top = 12
    y_bot = 34

    if no_signal:
        draw.text((12, y_top + 4), "NO SIGNAL", fill=1)
        draw.rectangle((x0, y_top, x1, y_bot), outline=1, fill=0)
    else:
        draw.rectangle((x0, y_top, x1, y_bot), outline=1, fill=0)
        fill_w = int(frac * mw + 0.5)
        if fill_w > 0:
            draw.rectangle((x0, y_top, x0 + fill_w - 1, y_bot), outline=1, fill=1)
        hx = x0 + int(hold_frac * mw + 0.5)
        hx = min(x1, max(x0, hx))
        draw.rectangle((hx, y_top - 2, min(hx + 1, x1), y_bot + 2), outline=1, fill=1)

    # L / R mini meters
    y_lr = 38
    h_lr = 8
    lx0, lx1 = 4, (w // 2) - 4
    rx0, rx1 = (w // 2) + 2, w - 5
    for label, x_a, x_b, rv in (("L", lx0, lx1, rms_l), ("R", rx0, rx1, rms_r)):
        draw.text((x_a, y_lr - 10), label, fill=1)
        draw.rectangle((x_a, y_lr, x_b, y_lr + h_lr), outline=1, fill=0)
        bw = x_b - x_a + 1
        f = min(1.0, rv / max(METER_REF_RMS, 1e-9))
        fw = int(f * bw + 0.5)
        if fw > 0:
            draw.rectangle((x_a, y_lr, x_a + fw - 1, y_lr + h_lr), outline=1, fill=1)

    draw.text((0, h - 18), f"rms {rms_m:.3f}", fill=1)
    draw.text((0, h - 9), f"pk {pk:.3f}", fill=1)


def main() -> None:
    global _hold_frac, _disp_rms

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    device_index, device_name = pick_input_device()
    sd.default.device = (device_index, None)

    sr_try = pick_samplerate(device_index)
    stream = None
    sr = sr_try
    for candidate in [sr_try, 48000, 44100]:
        try:
            stream = sd.InputStream(
                device=device_index,
                channels=2,
                samplerate=candidate,
                blocksize=BLOCK,
                dtype="float32",
                callback=_cb,
            )
            stream.start()
            sr = candidate
            break
        except Exception:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
                stream = None
    if stream is None:
        raise RuntimeError("Could not open InputStream")

    print(f"OLED level: [{device_index}] {device_name} @ {sr} Hz", flush=True)

    serial = i2c(port=1, address=I2C_ADDR)
    oled = sh1106(serial)
    size = oled.size
    frame_dt = 1.0 / max(1.0, DISPLAY_FPS)

    try:
        while running:
            t0 = time.perf_counter()
            with _lock:
                rms_m = _rms_mono
                pk = _peak_mono
                rl = _rms_l
                rr = _rms_r

            _disp_rms = (1.0 - RMS_SMOOTH) * _disp_rms + RMS_SMOOTH * rms_m
            frac = _level_frac(_disp_rms, pk)
            _hold_frac = max(frac, _hold_frac * PEAK_DECAY)

            no_signal = rms_m < NO_SIGNAL_RMS

            img = Image.new("1", size, 0)
            draw = ImageDraw.Draw(img)
            draw_meter(
                draw,
                size[0],
                size[1],
                0.0 if no_signal else frac,
                _hold_frac,
                _disp_rms,
                pk,
                rl,
                rr,
                no_signal,
            )
            oled.display(img)

            elapsed = time.perf_counter() - t0
            time.sleep(max(0.0, frame_dt - elapsed))

    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
        try:
            oled.clear()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FATAL:", e, file=sys.stderr)
        sys.exit(1)
