#!/usr/bin/env python3
"""
MIDI input probe for Raspberry Pi + Akai MPK (and similar).

Prints every MIDI byte string received on RtMidi input ports whose name contains "mpk"
(case-insensitive). Uses callbacks (same strategy as oled_midi_synth.py should use).

Usage:
  /home/uzan/Raspberri_Pi_Audio/.venv/bin/python /home/uzan/Raspberri_Pi_Audio/midi_listen_test.py

While it runs, play keys and twist knobs. Ctrl+C to stop.

Compare with ALSA (kernel path, independent of Python):
  aseqdump -p 28:0,28:1,28:2

Raw Software port (not in RtMidi — use this if keys only appear here):
  python midi_listen_test.py --amidi-software

If aseqdump shows events but this script does not, RtMidi/Python is misconfigured.
If neither shows events when you play keys, the MPK preset is not sending on these
ports (use Akai MPK Editor / change preset / check USB).
"""
from __future__ import annotations

import os
import pathlib
import signal
import sys
import time
from collections.abc import Callable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import rtmidi

MATCH = ("mpk",)
running = True


def list_mpk_ports() -> list[tuple[int, str]]:
    probe = rtmidi.MidiIn()
    try:
        n = probe.get_port_count()
        names = [probe.get_port_name(i) for i in range(n)]
    finally:
        probe.delete()
    out: list[tuple[int, str]] = []
    for i in range(n):
        if any(m in names[i].lower() for m in MATCH):
            out.append((i, names[i]))
    return out


def explain_byte(b: int) -> str:
    if 0x80 <= b <= 0xEF:
        hi = b & 0xF0
        ch = (b & 0x0F) + 1
        names = {
            0x80: "NoteOff",
            0x90: "NoteOn",
            0xA0: "PolyAT",
            0xB0: "CC",
            0xC0: "Prog",
            0xD0: "ChPress",
            0xE0: "PitchBend",
        }
        return f"{names.get(hi, '?')} ch{ch}"
    if b >= 0xF0:
        return f"sys {b:#04x}"
    return ""


def main_amidi_raw(software_only: bool) -> None:
    """Listen via `amidi -d` on MPK raw ports (Software port is not in RtMidi)."""
    global running
    running = True
    from midi_amidi_helpers import start_amidi_raw_threads

    if software_only:
        os.environ["RPI_SYNTH_MIDI_RAW"] = "software"
    else:
        os.environ["RPI_SYNTH_MIDI_RAW"] = "all"

    print("amidi raw MIDI (RPI_SYNTH_MIDI_RAW=%s). Play keys. Ctrl+C to quit.\n" % os.environ.get("RPI_SYNTH_MIDI_RAW"), flush=True)

    def stop(_s=None, _f=None) -> None:
        global running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    def dispatch(data: list[int]) -> None:
        hint = explain_byte(data[0]) if data else ""
        print(f"{time.monotonic():.3f}  amidi  {data!r}  {hint}", flush=True)

    threads = start_amidi_raw_threads(dispatch, lambda: running)
    if not threads:
        print("No raw ports selected. Check: amidi -l", file=sys.stderr, flush=True)
        sys.exit(1)
    try:
        while running:
            time.sleep(0.2)
    finally:
        running = False
        for t in threads:
            t.join(timeout=3.0)


def main() -> None:
    global running
    if "--amidi-software" in sys.argv:
        main_amidi_raw(software_only=True)
        return
    if "--amidi-all" in sys.argv:
        main_amidi_raw(software_only=False)
        return

    ports = list_mpk_ports()
    if not ports:
        print("No RtMidi input port name contains 'mpk'. Available inputs:", file=sys.stderr)
        p = rtmidi.MidiIn()
        try:
            for i in range(p.get_port_count()):
                print(" ", i, repr(p.get_port_name(i)), file=sys.stderr)
        finally:
            p.delete()
        sys.exit(1)

    print("RtMidi will open these inputs:", flush=True)
    for idx, name in ports:
        print(f"  [{idx}] {name}", flush=True)
    print("\nPlay keys / pads / knobs. Ctrl+C to quit.\n", flush=True)

    ins: list[rtmidi.MidiIn] = []

    def stop(_s=None, _f=None) -> None:
        global running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    def make_cb(port_name: str) -> Callable:
        def cb(event: tuple, _data: object) -> None:
            data, delta = event
            if not data:
                return
            b = list(data)
            hint = explain_byte(b[0]) if b else ""
            print(
                f"{time.monotonic():.3f}  {port_name[:40]:<40}  "
                f"dt={delta*1000:.2f}ms  {b!r}  {hint}",
                flush=True,
            )

        return cb

    for idx, name in ports:
        m = rtmidi.MidiIn()
        try:
            m.open_port(idx)
            m.set_callback(make_cb(name))
            ins.append(m)
            print(f"OK opened [{idx}]", flush=True)
        except Exception as e:
            print(f"FAILED to open [{idx}] {name}: {e}", file=sys.stderr, flush=True)
            try:
                m.delete()
            except Exception:
                pass

    if not ins:
        print("No ports opened.", file=sys.stderr)
        sys.exit(1)

    try:
        while running:
            time.sleep(0.2)
    finally:
        running = False
        for m in ins:
            try:
                m.close_port()
            except Exception:
                pass
            try:
                m.delete()
            except Exception:
                pass


if __name__ == "__main__":
    main()
