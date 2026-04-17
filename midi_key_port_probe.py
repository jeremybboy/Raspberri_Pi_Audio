#!/usr/bin/env python3
"""
Map: "I play a key → which port shows bytes?"

Read-only: listens on all MPK-related MIDI *inputs* for a few seconds and counts
messages per port (RtMidi sequencer ports + raw `amidi` IO lines).

Usage (play keys/pads during the window):

  /home/uzan/Raspberri_Pi_Audio/.venv/bin/python /home/uzan/Raspberri_Pi_Audio/midi_key_port_probe.py
  /home/uzan/Raspberri_Pi_Audio/.venv/bin/python /home/uzan/Raspberri_Pi_Audio/midi_key_port_probe.py --seconds 25

Requires: python-rtmidi, mido, alsa-utils (amidi).
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import rtmidi
from mido.parser import Parser

from midi_amidi_helpers import parse_amidi_io_ports


def main() -> None:
    ap = argparse.ArgumentParser(description="Count MIDI messages per MPK input port.")
    ap.add_argument(
        "--seconds",
        type=float,
        default=20.0,
        help="How long to listen (default 20).",
    )
    args = ap.parse_args()

    counts: dict[str, int] = {}
    lock = threading.Lock()
    stop = threading.Event()

    def bump(label: str, n: int = 1) -> None:
        with lock:
            counts[label] = counts.get(label, 0) + n

    threads: list[threading.Thread] = []

    # --- RtMidi inputs (MPK) ---
    probe = rtmidi.MidiIn()
    try:
        nports = probe.get_port_count()
        names = [probe.get_port_name(i) for i in range(nports)]
    finally:
        probe.delete()

    rtmidi_ins: list[tuple[rtmidi.MidiIn, str]] = []
    for i in range(nports):
        name = names[i]
        if "mpk" not in name.lower():
            continue
        label = f"RtMidi IN [{i}] {name}"

        def make_cb(lab: str):
            def _cb(event: tuple, _d: object) -> None:
                data, _dt = event
                if data:
                    bump(lab, 1)

            return _cb

        m = rtmidi.MidiIn()
        try:
            m.open_port(i)
            m.set_callback(make_cb(label))
            rtmidi_ins.append((m, label))
            print(f"OK  {label}", flush=True)
        except Exception as e:
            print(f"SKIP {label}: {e}", file=sys.stderr, flush=True)
            try:
                m.delete()
            except Exception:
                pass

    # --- Raw amidi (each IO line) ---
    try:
        raw_list = parse_amidi_io_ports(mpk_only=True)
    except RuntimeError as e:
        print(f"amidi list: {e}", file=sys.stderr, flush=True)
        raw_list = []

    def amidi_thread(hw: str, human_name: str) -> None:
        label = f"amidi -d {hw} ({human_name})"
        try:
            import subprocess

            proc = subprocess.Popen(
                ["amidi", "-p", hw, "-d"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            print(f"SKIP {label}: {e}", file=sys.stderr, flush=True)
            return

        parser = Parser()
        print(f"OK  {label}", flush=True)
        try:
            assert proc.stdout is not None
            while not stop.is_set():
                line = proc.stdout.readline()
                if not line:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.01)
                    continue
                for token in line.split():
                    try:
                        b = int(token, 16)
                    except ValueError:
                        continue
                    parser.feed(bytes([b]))
                    for _msg in parser:
                        bump(label, 1)
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=1.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    for hw, hname in raw_list:
        t = threading.Thread(target=amidi_thread, args=(hw, hname), daemon=True)
        t.start()
        threads.append(t)

    print("", flush=True)
    print(
        f">>> Play keys, pads, and wheels for {args.seconds:.0f} s … (Ctrl+C to stop early)\n",
        flush=True,
    )

    t0 = time.monotonic()

    def wait() -> None:
        try:
            while time.monotonic() - t0 < args.seconds:
                if stop.is_set():
                    return
                time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()

    try:
        wait()
    finally:
        if not stop.is_set():
            stop.set()

    time.sleep(0.3)
    for m, label in rtmidi_ins:
        try:
            m.close_port()
        except Exception:
            pass
        try:
            m.delete()
        except Exception:
            pass

    for t in threads:
        t.join(timeout=2.0)

    print("", flush=True)
    print("=== Counts (higher = bytes arrived on that path) ===", flush=True)
    if not counts:
        print("No MIDI messages received on any opened port.", flush=True)
        print(
            "Try another preset (User vs DAW), firmware, or USB port; see Readme troubleshooting.",
            flush=True,
        )
        return

    ranked = sorted(counts.items(), key=lambda x: -x[1])
    w = max(len(k) for k in counts.keys())
    for k, v in ranked:
        print(f"{v:6d}  {k}", flush=True)


if __name__ == "__main__":
    main()
