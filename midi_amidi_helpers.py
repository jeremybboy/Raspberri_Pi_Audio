"""
ALSA raw MIDI (amidi) helpers for MPK mini IV.

RtMidi exposes only three ALSA *sequencer* inputs (MIDI / Din / DAW). The MPK also
presents a Software Port on raw MIDI (see `amidi -l` as hw:?,0,2) that does not
appear in RtMidi — keys routed there need this path.

See: scripts/midi_connection_check.sh for full diagnostics.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from mido.parser import Parser


def parse_amidi_io_ports(mpk_only: bool = True) -> list[tuple[str, str]]:
    """
    Parse `amidi -l` for bidirectional (IO) raw ports.

    Returns [(hw:card,dev,sub, name), ...]
    """
    try:
        out = subprocess.check_output(
            ["amidi", "-l"], text=True, stderr=subprocess.DEVNULL, timeout=5
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise RuntimeError("amidi not found or failed; install alsa-utils") from e

    ports: list[tuple[str, str]] = []
    for line in out.splitlines():
        line = line.strip()
        m = re.match(r"^(IO|I)\s+(hw:\d+,\d+,\d+)\s+(.+)$", line)
        if not m:
            continue
        _direction, hw, name = m.group(1), m.group(2), m.group(3).strip()
        if mpk_only and "mpk" not in name.lower():
            continue
        ports.append((hw, name))
    return ports


def filter_raw_ports_by_env(ports: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """
    RPI_SYNTH_MIDI_RAW:
      unset or 'software' (default): only ports whose name contains 'Software'
      'all': every IO MPK raw port (may duplicate RtMidi for MIDI/DAW — use with care)
      '0' or 'off': none
    """
    raw = os.environ.get("RPI_SYNTH_MIDI_RAW", "software").strip().lower()
    if raw in ("0", "off", "no", "false"):
        return []
    if raw == "all":
        return list(ports)
    if raw in ("software", "", "default"):
        return [(hw, n) for hw, n in ports if "software" in n.lower()]
    # substring match e.g. RPI_SYNTH_MIDI_RAW=midi
    return [(hw, n) for hw, n in ports if raw in n.lower()]


def amidi_raw_worker(
    hw_device: str,
    label: str,
    dispatch: Callable[[list[int]], None],
    running_ref: Callable[[], bool],
) -> None:
    """
    Read `amidi -p HW -d` hex dump, parse with mido.Parser, dispatch full messages.
    """
    try:
        proc = subprocess.Popen(
            ["amidi", "-p", hw_device, "-d"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        print(f"amidi FAILED start [{hw_device}] {label}: {e}", file=sys.stderr, flush=True)
        return

    parser = Parser()
    print(f"MIDI raw (amidi): [{hw_device}] {label}", flush=True)

    try:
        assert proc.stdout is not None
        while running_ref():
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    err = proc.stderr.read() if proc.stderr else ""
                    if err:
                        print(f"amidi stderr {hw_device}: {err}", file=sys.stderr, flush=True)
                    break
                time.sleep(0.01)
                continue
            for token in line.split():
                try:
                    b = int(token, 16)
                except ValueError:
                    continue
                parser.feed(bytes([b]))
                for msg in parser:
                    if msg.type == "sysex":
                        continue
                    try:
                        data = list(msg.bytes())
                    except Exception:
                        continue
                    dispatch(data)
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def start_amidi_raw_threads(
    dispatch_bytes: Callable[[list[int]], None],
    running_ref: Callable[[], bool],
) -> list[threading.Thread]:
    """Start threads for filtered raw ports; return threads to join."""
    try:
        all_ports = parse_amidi_io_ports(mpk_only=True)
    except RuntimeError as e:
        print(f"amidi list skipped: {e}", file=sys.stderr, flush=True)
        return []

    chosen = filter_raw_ports_by_env(all_ports)
    if not chosen:
        return []

    threads: list[threading.Thread] = []
    for hw, name in chosen:
        t = threading.Thread(
            target=amidi_raw_worker,
            args=(hw, name, dispatch_bytes, running_ref),
            daemon=True,
            name=f"amidi-{hw}",
        )
        t.start()
        threads.append(t)
    return threads
