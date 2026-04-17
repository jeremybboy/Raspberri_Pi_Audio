#!/usr/bin/env bash
# MIDI connection checklist for MPK mini IV + Raspberry Pi (Phases 1–2 of the test plan).
# Run: bash /home/uzan/Raspberri_Pi_Audio/scripts/midi_connection_check.sh

set -euo pipefail

echo "=== Phase 1: USB (expect AKAI MPK mini IV) ==="
lsusb | grep -iE 'akai|inmusic' || lsusb | head -15
echo

echo "=== Phase 2a: aconnect -l (client 28 = MPK on this machine; yours may differ) ==="
aconnect -l
echo

echo "=== Phase 2b: aseqdump -l (sequencer inputs — Software often missing here) ==="
aseqdump -l | head -30
echo

echo "=== Phase 2c: amidi -l (raw ports — includes Software IO hw:?,0,2) ==="
amidi -l
echo

echo "=== Manual tests while playing keys ==="
echo "  aseqdump -p 28:0,28:1,28:2"
echo "  /path/to/.venv/bin/python /path/to/midi_listen_test.py"
echo "  /path/to/.venv/bin/python /path/to/midi_listen_test.py --amidi-software"
echo "  /path/to/.venv/bin/python /path/to/midi_key_port_probe.py   # counts per port while you play"
echo "  /path/to/.venv/bin/python /path/to/oled_midi_synth.py"
echo
echo "oled_midi_synth opens RtMidi + raw Software (amidi) by default (RPI_SYNTH_MIDI_RAW=software)."
