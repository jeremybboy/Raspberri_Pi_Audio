#!/usr/bin/env python3
"""
MIDI-driven polyphonic synth: Akai MPK (USB MIDI) -> numpy oscillators + ADSR ->
Behringer USB Audio CODEC output. SH1106 OLED shows a live output waveform strip
and one line of status (waveform + active notes).

Run (from project venv):
  /home/uzan/Raspberri_Pi_Audio/.venv/bin/python /home/uzan/Raspberri_Pi_Audio/oled_midi_synth.py

System: libasound2-dev was required to pip-install python-rtmidi on Raspberry Pi OS.

MPK Mini 3/4 exposes several virtual ports (MIDI / DIN / DAW). Keys may appear on any one of them
depending on the preset. By default this script opens **all** MPK ports at once so note data is not missed.

Optional filter (substring in port name, case-insensitive):
  RPI_SYNTH_MIDI_PORT=daw   # only ports whose name contains "daw"
  RPI_SYNTH_MIDI_DEBUG=1    # print incoming MIDI bytes to stderr (sanity check)
"""
from __future__ import annotations

import math
import os
import queue
import signal
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass

import numpy as np
import sounddevice as sd

import rtmidi
from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from PIL import Image, ImageDraw, ImageFont

# ---------- CONFIG ----------
DEVICE_MATCH = ["USB Audio CODEC"]
MIDI_MATCH = ["mpk"]
I2C_ADDR = 0x3C

BLOCK = 256
DISPLAY_FPS = 18.0
NUM_VOICES = 8

# ADSR (seconds)
ATTACK = 0.008
DECAY = 0.06
SUSTAIN = 0.65  # level 0..1
RELEASE = 0.18

WAVE_NAMES = ("SIN", "TRI", "SAW", "SQR")

OLED_W, OLED_H = 128, 64
TEXT_H = 10
SCOPE_TOP = TEXT_H
SCOPE_H = OLED_H - SCOPE_TOP

# Recent mono samples for scope (about ~85 ms @ 48 kHz)
SCOPE_RING_MAX = 4096
# ---------------------------


TWO_PI = 2.0 * math.pi


def mtof(note: int) -> float:
    return 440.0 * (2.0 ** ((float(note) - 69.0) / 12.0))


def osc_fn(phase: float, wave: int) -> float:
    """Single-sample oscillator, phase in [0, 2pi)."""
    x = phase % TWO_PI
    if wave == 0:
        return math.sin(x)
    if wave == 1:
        # Triangle -1..1
        p = x / TWO_PI
        return 4.0 * abs(p - 0.5) - 1.0
    if wave == 2:
        # Saw -1..1 rising
        return 2.0 * (x / TWO_PI) - 1.0
    # square
    return 1.0 if x < math.pi else -1.0


@dataclass
class Voice:
    active: bool = False
    note: int = 0
    vel: float = 0.0
    freq: float = 0.0
    phase: float = 0.0
    wave: int = 0
    env: float = 0.0
    stage: int = 0  # 0 atk 1 dcy 2 sus 3 rel 4 idle
    sustain_level: float = SUSTAIN
    rel_per_sample: float = 0.0


class VoiceEngine:
    def __init__(self, sr: int) -> None:
        self.sr = sr
        self._atk_step = 1.0 / max(1, int(ATTACK * sr))
        self._dcy_per_sample = (1.0 - SUSTAIN) / max(1, int(DECAY * sr))
        self._rel_samples = max(1, int(RELEASE * sr))
        self.voices: list[Voice] = [Voice() for _ in range(NUM_VOICES)]
        self.wave_global: int = 0
        self._lock = threading.Lock()

    def set_wave(self, w: int) -> None:
        w = int(w) % 4
        with self._lock:
            self.wave_global = w
            for v in self.voices:
                if v.active:
                    v.wave = w

    def note_on(self, note: int, vel: int) -> None:
        if vel <= 0:
            self.note_off(note)
            return
        vel_f = min(1.0, max(0.0, vel / 127.0))
        with self._lock:
            w = self.wave_global
            for v in self.voices:
                if v.active and v.note == note:
                    v.vel = vel_f
                    v.freq = mtof(note)
                    v.wave = w
                    v.stage = 0
                    v.env = 0.0
                    return
            for v in self.voices:
                if not v.active:
                    v.active = True
                    v.note = note
                    v.vel = vel_f
                    v.freq = mtof(note)
                    v.phase = 0.0
                    v.wave = w
                    v.stage = 0
                    v.env = 0.0
                    v.sustain_level = SUSTAIN
                    return
            v = self.voices[0]
            v.active = True
            v.note = note
            v.vel = vel_f
            v.freq = mtof(note)
            v.phase = 0.0
            v.wave = w
            v.stage = 0
            v.env = 0.0

    def note_off(self, note: int) -> None:
        with self._lock:
            for v in self.voices:
                if v.active and v.note == note:
                    v.stage = 3
                    v.rel_per_sample = max(v.env, 1e-9) / float(self._rel_samples)

    def _tick_env(self, v: Voice) -> None:
        if v.stage == 0:
            v.env += self._atk_step
            if v.env >= 1.0:
                v.env = 1.0
                v.stage = 1
        elif v.stage == 1:
            v.env -= self._dcy_per_sample
            if v.env <= v.sustain_level:
                v.env = v.sustain_level
                v.stage = 2
        elif v.stage == 2:
            v.env = v.sustain_level
        elif v.stage == 3:
            v.env -= v.rel_per_sample
            if v.env <= 0.0:
                v.env = 0.0
                v.active = False
                v.stage = 4

    def render_fixed(self, frames: int) -> np.ndarray:
        """Render block; envelope + osc in one pass per voice (real-time callback)."""
        out = np.zeros(frames, dtype=np.float64)
        with self._lock:
            for v in self.voices:
                if not v.active:
                    continue
                dph = TWO_PI * v.freq / float(self.sr)
                ph = v.phase
                for i in range(frames):
                    self._tick_env(v)
                    out[i] += osc_fn(ph, v.wave) * v.env * v.vel
                    ph = (ph + dph) % TWO_PI
                v.phase = ph
        return out

running = True
_scope_lock = threading.Lock()
_scope_ring: deque[float] = deque(maxlen=SCOPE_RING_MAX)
_status_line = "SIN  ---"
def pick_output_device() -> tuple[int, str]:
    devs = sd.query_devices()
    for i, d in enumerate(devs):
        if d.get("max_output_channels", 0) <= 0:
            continue
        name = d.get("name", "")
        if any(m.lower() in name.lower() for m in DEVICE_MATCH):
            return i, name
    raise RuntimeError("USB Audio CODEC output not found; connect Behringer interface.")


def pick_samplerate(device_index: int) -> int:
    info = sd.query_devices(device_index, "output")
    sr = info.get("default_samplerate")
    if sr is not None:
        return int(round(float(sr)))
    return 48000


def list_mpk_input_ports() -> list[tuple[int, str]]:
    """Return [(port_index, name), ...] for Akai MPK devices."""
    probe = rtmidi.MidiIn()
    try:
        n = probe.get_port_count()
        names = [probe.get_port_name(i) for i in range(n)]
    finally:
        probe.delete()

    mpk: list[tuple[int, str]] = []
    for i in range(n):
        name = names[i]
        if any(m.lower() in name.lower() for m in MIDI_MATCH):
            mpk.append((i, name))

    filt = os.environ.get("RPI_SYNTH_MIDI_PORT", "").strip().lower()
    if filt and filt in ("daw", "midi", "din"):
        mpk = [(i, nm) for i, nm in mpk if filt in nm.lower()]

    if not mpk:
        raise RuntimeError(
            f"No MIDI input matched {MIDI_MATCH!r}"
            + (f" and filter {filt!r}" if filt else "")
            + f"; available: {names!r}"
        )
    return mpk


_midi_debug_left = 64


def handle_midi_bytes(data: list[int], engine: VoiceEngine, eventq: queue.Queue[str]) -> None:
    """Handle one ALSA MIDI message (rtmidi gives full voice messages)."""
    global _midi_debug_left
    if not data:
        return
    if data[0] == 0xF0:
        return
    if os.environ.get("RPI_SYNTH_MIDI_DEBUG", "").strip() in ("1", "true", "yes"):
        if _midi_debug_left > 0:
            print("MIDI:", [hex(b) for b in data], flush=True)
            _midi_debug_left -= 1

    status = data[0] & 0xF0
    if status == 0x90:  # note on (any channel)
        note = data[1]
        vel = data[2] if len(data) > 2 else 0
        engine.note_on(note, vel)
        eventq.put("midi")
    elif status == 0x80:  # note off
        note = data[1]
        engine.note_off(note)
        eventq.put("midi")
    elif status == 0xC0:  # program change
        prog = data[1] if len(data) > 1 else 0
        engine.set_wave(prog % 4)
        eventq.put("midi")


def midi_worker(port_index: int, port_name: str, engine: VoiceEngine, eventq: queue.Queue[str]) -> None:
    """One RtMidiIn per port; MPK exposes multiple virtual cables."""
    midi_in = rtmidi.MidiIn()
    try:
        midi_in.open_port(port_index)
        print(f"MIDI listen: [{port_index}] {port_name}", flush=True)
        while running:
            msg = midi_in.get_message()
            if msg is None:
                time.sleep(0.001)
                continue
            data, _ = msg
            handle_midi_bytes(list(data), engine, eventq)
    finally:
        try:
            midi_in.close_port()
        except Exception:
            pass
        try:
            midi_in.delete()
        except Exception:
            pass


def build_status(engine: VoiceEngine) -> str:
    with engine._lock:
        w = engine.wave_global
        wname = WAVE_NAMES[w]
    active_notes = sorted({v.note for v in engine.voices if v.active})
    if not active_notes:
        notes_s = "---"
    elif len(active_notes) <= 4:
        notes_s = ",".join(note_name(n) for n in active_notes)
    else:
        notes_s = f"{note_name(active_notes[0])}-{note_name(active_notes[-1])}({len(active_notes)})"
    return f"{wname}  {notes_s}"


def note_name(n: int) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octv = (n // 12) - 1
    return names[n % 12] + str(octv)


def make_audio_callback(engine: VoiceEngine):
    def callback(outdata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            print("Audio status:", status, file=sys.stderr)
        mono = engine.render_fixed(frames)
        # soft clip
        mono = np.tanh(mono * 0.9)
        if outdata.shape[1] >= 2:
            outdata[:, 0] = mono
            outdata[:, 1] = mono
        else:
            outdata[:, 0] = mono
        with _scope_lock:
            _scope_ring.extend(mono.astype(float).tolist())

    return callback


def draw_scope(
    draw: ImageDraw.ImageDraw,
    samples: np.ndarray,
    width: int,
    y0: int,
    height: int,
) -> None:
    if samples.size < 2:
        return
    cols = width
    n = samples.size
    bin_w = n / cols
    for col in range(cols):
        lo = int(col * bin_w)
        hi = int((col + 1) * bin_w)
        hi = max(lo + 1, hi)
        seg = samples[lo:hi]
        mn = float(np.min(seg))
        mx = float(np.max(seg))
        # map -1..1 to y (top=high amp positive could be top or bottom; scope: top=min y)
        y1 = y0 + int((1.0 - mx) * 0.5 * height)
        y2 = y0 + int((1.0 - mn) * 0.5 * height)
        y1 = max(y0, min(y0 + height - 1, y1))
        y2 = max(y0, min(y0 + height - 1, y2))
        if y2 < y1:
            y1, y2 = y2, y1
        draw.line((col, y1, col, y2), fill=1)


def main() -> None:
    global running, _status_line

    out_idx, out_name = pick_output_device()
    sr = pick_samplerate(out_idx)
    engine = VoiceEngine(sr)

    mpk_ports = list_mpk_input_ports()
    print(f"Output: [{out_idx}] {out_name} @ {sr} Hz", flush=True)
    print(f"MIDI: opening {len(mpk_ports)} MPK port(s)", flush=True)

    eventq: queue.Queue[str] = queue.Queue()
    midi_threads: list[threading.Thread] = []
    for idx, pname in mpk_ports:
        t = threading.Thread(
            target=midi_worker,
            args=(idx, pname, engine, eventq),
            daemon=True,
        )
        t.start()
        midi_threads.append(t)

    stream = sd.OutputStream(
        device=out_idx,
        channels=2,
        samplerate=sr,
        blocksize=BLOCK,
        dtype="float32",
        callback=make_audio_callback(engine),
    )

    serial = i2c(port=1, address=I2C_ADDR)
    oled = sh1106(serial)
    size = oled.size

    try:
        stream.start()
    except Exception as e:
        running = False
        for t in midi_threads:
            t.join(timeout=2.0)
        raise RuntimeError(f"Failed to start audio: {e}") from e

    frame_dt = 1.0 / max(1.0, DISPLAY_FPS)
    last_status_t = 0.0
    font = ImageFont.load_default()

    def handle_signal(signum, frame) -> None:
        global running
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        while running:
            t0 = time.perf_counter()
            now = time.monotonic()
            # throttle status text ~10 Hz
            if now - last_status_t > 0.1:
                _status_line = build_status(engine)
                last_status_t = now
            while True:
                try:
                    eventq.get_nowait()
                except queue.Empty:
                    break

            with _scope_lock:
                if len(_scope_ring) < 2:
                    snap = np.zeros(0, dtype=np.float32)
                else:
                    snap = np.asarray(list(_scope_ring), dtype=np.float32)

            img = Image.new("1", size, 0)
            draw = ImageDraw.Draw(img)
            draw.rectangle((0, 0, OLED_W - 1, TEXT_H - 1), outline=0, fill=0)
            draw.text((2, 1), _status_line[:32], fill=1, font=font)
            draw.line((0, TEXT_H, OLED_W, TEXT_H), fill=1)

            draw_scope(draw, snap, OLED_W, SCOPE_TOP, SCOPE_H)
            oled.display(img)

            elapsed = time.perf_counter() - t0
            time.sleep(max(0.0, frame_dt - elapsed))
    finally:
        running = False
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
        try:
            oled.clear()
        except Exception:
            pass
        for t in midi_threads:
            t.join(timeout=2.0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FATAL:", e, file=sys.stderr)
        sys.exit(1)
