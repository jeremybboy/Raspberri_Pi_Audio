#!/usr/bin/env python3
"""
Real-time line-in spectrum bars on SH1106 OLED (e.g. Behringer UCA202 / USB Audio CODEC).
Mono mix (L+R)/2, 16 log-spaced bands, throttled display refresh.
"""
from __future__ import annotations

import math
import signal
import sys
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd

from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from PIL import Image, ImageDraw

# ---------- CONFIG ----------
DEVICE_MATCH = ["USB Audio CODEC"]
I2C_ADDR = 0x3C

BLOCK = 1024
FFT_SIZE = 2048
NUM_BARS = 16

# Display refresh (Hz); keep modest for Pi + full framebuffer updates
DISPLAY_FPS = 18.0

# Silence gate (same order of magnitude as BPM script)
NO_SIGNAL_RMS = 0.003

# Log-spaced band edges (Hz)
F_LO_HZ = 100.0

# dB mapping for bar height
DB_FLOOR = -58.0
DB_CEIL = -10.0

# EMA smoothing on normalized bar heights
EMA_ALPHA = 0.35

# Per-bin peak line (decay each frame when active)
PEAK_DECAY = 0.86

# Idle animation (no audible signal)
IDLE_AMP_FRAC = 0.22  # max fraction of bar area used by standby motion
# ---------------------------

running = True
_buf_lock = threading.Lock()
_mono_ring: deque[float] = deque(maxlen=FFT_SIZE * 4)
_last_rms = 0.0
_device_index: int | None = None
_device_name = "?"


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


def open_input_stream(device_index: int, samplerate: int):
    return sd.InputStream(
        device=device_index,
        channels=2,
        samplerate=samplerate,
        blocksize=BLOCK,
        dtype="float32",
        callback=_audio_callback,
    )


def _audio_callback(indata, frames, time_info, status):
    global _last_rms
    mono = indata.mean(axis=1).astype(np.float32)
    rms = float(np.sqrt(np.mean(mono * mono)))
    _last_rms = rms
    with _buf_lock:
        _mono_ring.extend(mono.tolist())


def handle_signal(signum, frame):
    global running
    running = False


def _log_bin_edges(sr: int, n_fft: int, n_bars: int) -> np.ndarray:
    nyq = 0.5 * sr * 0.995
    lo = max(F_LO_HZ, sr / n_fft)
    hi = max(lo * 1.05, nyq)
    return np.logspace(np.log10(lo), np.log10(hi), n_bars + 1)


def spectrum_bars(x: np.ndarray, sr: int, n_fft: int, n_bars: int) -> np.ndarray:
    """Return normalized bar heights in [0, 1], shape (n_bars,)."""
    x = x.astype(np.float64)
    win = np.hanning(len(x)).astype(np.float64)
    xw = x * win
    spec = np.fft.rfft(xw, n=n_fft)
    psd = (np.abs(spec) ** 2).astype(np.float64)
    psd[0] = 0.0

    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)
    edges = _log_bin_edges(sr, n_fft, n_bars)
    out_db = np.empty(n_bars, dtype=np.float64)
    for i in range(n_bars):
        f0, f1 = edges[i], edges[i + 1]
        m = (freqs >= f0) & (freqs < f1)
        if not np.any(m):
            out_db[i] = DB_FLOOR
        else:
            p = float(np.sum(psd[m]))
            out_db[i] = 10.0 * np.log10(p + 1e-18)

    t = (out_db - DB_FLOOR) / (DB_CEIL - DB_FLOOR)
    return np.clip(t, 0.0, 1.0).astype(np.float32)


def _draw_header(draw: ImageDraw.ImageDraw, w: int) -> None:
    """Title only (no rule line — keeps the spectrum area clean)."""
    draw.text((3, 0), "spectrum", fill=1)


def _draw_idle_body(
    draw: ImageDraw.ImageDraw,
    w: int,
    top: int,
    bottom: int,
    phase: float,
) -> None:
    """Soft standby motion instead of a harsh error string."""
    usable = max(4, bottom - top)
    base_y = bottom
    cols = 40
    for k in range(cols):
        x = 4 + (k * (w - 8)) // max(1, cols - 1)
        slow = math.sin(phase * 1.15 + k * 0.31)
        fast = 0.35 * math.sin(phase * 2.6 + k * 0.62)
        amp = (0.35 + 0.65 * (0.5 * (slow + 1.0))) * IDLE_AMP_FRAC + fast * 0.04
        amp = max(0.04, min(IDLE_AMP_FRAC + 0.06, amp))
        hh = max(2, int(amp * usable + 0.5))
        y0 = base_y - hh
        draw.rectangle((x, y0, x + 1, base_y), outline=1, fill=1)


def _draw_footer(draw: ImageDraw.ImageDraw, w: int, h: int, text: str) -> None:
    draw.text((3, h - 9), text[:28], fill=1)


def draw_frame(
    draw: ImageDraw.ImageDraw,
    size: tuple[int, int],
    bars: np.ndarray,
    peak: np.ndarray,
    rms: float,
    no_signal: bool,
    phase: float,
) -> None:
    w, h = size
    draw.rectangle((0, 0, w - 1, h - 1), outline=0, fill=0)
    _draw_header(draw, w)

    top = 12
    bottom = h - 13
    usable_h = max(6, bottom - top)
    n = len(bars)

    if no_signal:
        _draw_idle_body(draw, w, top, bottom, phase)
        dots = int(phase * 1.8) % 4
        _draw_footer(draw, w, h, "listening" + ("." * dots))
        return

    # Symmetric blend: pleasanter "club meter" look on a tiny display
    disp = np.maximum(bars, bars[::-1]).astype(np.float32, copy=False)

    gap = 1
    inner_w = w - 6
    bar_w = max(2, (inner_w - gap * (n - 1)) // n)
    x0 = 3

    for i in range(n):
        bh = int(float(disp[i]) * usable_h + 0.5)
        bh = max(0, min(bh, usable_h))
        x1 = min(w - 4, x0 + bar_w - 1)
        if x1 < x0:
            break
        if bh > 0:
            y0 = bottom - bh
            draw.rectangle((x0, y0, x1, bottom), outline=1, fill=1)
            cap_h = min(3, bh)
            draw.rectangle((x0, y0, x1, y0 + cap_h - 1), outline=1, fill=1)

        ph = int(float(peak[i]) * usable_h + 0.5)
        ph = max(0, min(ph, usable_h))
        if ph > 0:
            yp = bottom - ph
            cx = (x0 + x1) // 2
            draw.line((cx, yp, cx, yp - 1), fill=1, width=1)

        x0 = x1 + gap + 1

    _draw_footer(draw, w, h, f"lvl {rms:.2f}")


def main() -> None:
    global running, _device_index, _device_name

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    _device_index, _device_name = pick_input_device()
    sd.default.device = (_device_index, None)

    sr = pick_samplerate(_device_index)
    stream = None
    last_sr = None
    for candidate in [sr, 48000, 44100]:
        try:
            stream = open_input_stream(_device_index, candidate)
            stream.start()
            last_sr = candidate
            break
        except Exception:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
                stream = None
    if stream is None or last_sr is None:
        raise RuntimeError(f"Could not open InputStream for device {_device_index}")

    sr = last_sr
    print(f"device[{_device_index}] {_device_name} @ {sr} Hz", flush=True)

    serial = i2c(port=1, address=I2C_ADDR)
    oled = sh1106(serial)
    size = oled.size

    smoothed = np.zeros(NUM_BARS, dtype=np.float32)
    peak_hold = np.zeros(NUM_BARS, dtype=np.float32)
    frame_dt = 1.0 / max(1.0, DISPLAY_FPS)

    try:
        while running:
            t0 = time.perf_counter()
            phase = time.monotonic()
            with _buf_lock:
                if len(_mono_ring) >= FFT_SIZE:
                    snap = np.asarray(
                        list(_mono_ring)[-FFT_SIZE:], dtype=np.float32
                    )
                else:
                    snap = None

            img = Image.new("1", size, 0)
            draw = ImageDraw.Draw(img)

            rms = _last_rms
            no_signal = rms < NO_SIGNAL_RMS

            if snap is None or no_signal:
                draw_frame(draw, size, smoothed, peak_hold, rms, True, phase)
                smoothed *= 0.88
                peak_hold *= 0.90
            else:
                raw = spectrum_bars(snap, sr, FFT_SIZE, NUM_BARS)
                smoothed = (EMA_ALPHA * raw + (1.0 - EMA_ALPHA) * smoothed).astype(
                    np.float32
                )
                disp = np.maximum(smoothed, smoothed[::-1])
                peak_hold = np.maximum(disp, peak_hold * PEAK_DECAY)
                draw_frame(draw, size, smoothed, peak_hold, rms, False, phase)

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
