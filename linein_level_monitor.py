#!/usr/bin/env python3
"""
Live terminal level meter for USB line-in calibration (Behringer UCA202 / USB Audio CODEC).
Runs until Ctrl+C: RMS, peak, dBFS (approx), and an ASCII bar so you can confirm signal in software.
"""
from __future__ import annotations

import signal
import sys
import threading
import time

import numpy as np
import sounddevice as sd

# ---------- CONFIG ----------
DEVICE_MATCH = ["USB Audio CODEC"]
BLOCK = 1024

# Terminal refresh (Hz)
UI_FPS = 25.0

# ASCII meter width
BAR_WIDTH = 44

# Ballistic smoothing (higher = snappier peak display)
PEAK_DECAY = 0.92

# Reference for mapping linear level to bar (float32 nominal +/-1.0); lower = more sensitive
BAR_REF_RMS = 0.035
# ---------------------------

_running = True
_lock = threading.Lock()
_rms = 0.0
_peak = 0.0
_hold_peak = 0.0
_stream_status: str = ""


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
    global _rms, _peak, _stream_status
    mono = indata.mean(axis=1).astype(np.float32)
    rms = float(np.sqrt(np.mean(mono * mono)))
    peak = float(np.max(np.abs(mono)))
    st = ""
    if status:
        st = str(status)
    with _lock:
        _rms = rms
        _peak = peak
        if st:
            _stream_status = st


def _handle_signal(signum, frame):
    global _running
    _running = False


def _dbfs_linear(x: float) -> float:
    """Rough dBFS for visualization (0 dBFS ~= full-scale sine)."""
    if x <= 1e-9:
        return -90.0
    return float(20.0 * np.log10(x))


def main() -> None:
    global _running, _hold_peak  # hold updated in UI loop for ballistic meter

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

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

    print(
        f"Listening: [{device_index}] {device_name} @ {sr} Hz — Ctrl+C to stop\n",
        flush=True,
    )

    frame_dt = 1.0 / max(1.0, UI_FPS)
    try:
        while _running:
            t0 = time.perf_counter()
            with _lock:
                rms = _rms
                peak = _peak
                st = _stream_status

            _hold_peak = max(peak, _hold_peak * PEAK_DECAY)
            # Bar from RMS and peak so quiet RMS still shows hits
            level = max(rms, _hold_peak * 0.85)
            frac = min(1.0, level / max(BAR_REF_RMS, 1e-9))
            n = int(frac * BAR_WIDTH + 0.5)
            n = max(0, min(BAR_WIDTH, n))
            bar = "#" * n + "." * (BAR_WIDTH - n)

            rms_db = _dbfs_linear(rms)
            pk_db = _dbfs_linear(peak)
            tail = f"  |{bar}|" if not st else f"  STATUS {st}"
            line = (
                f"RMS {rms:7.5f} ({rms_db:+5.1f} dBFS)  "
                f"peak {peak:7.5f} ({pk_db:+5.1f} dBFS)  hold {_hold_peak:7.5f}"
                f"{tail}"
            )
            sys.stdout.write("\r" + line.ljust(min(len(line) + 8, 160)))
            sys.stdout.flush()

            elapsed = time.perf_counter() - t0
            time.sleep(max(0.0, frame_dt - elapsed))

    finally:
        sys.stdout.write("\n")
        sys.stdout.flush()
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FATAL:", e, file=sys.stderr)
        sys.exit(1)
