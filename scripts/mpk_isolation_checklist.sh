#!/usr/bin/env bash
# MPK mini IV isolation checklist (Pi side + steps you do by hand).
# Run: bash /home/uzan/Raspberri_Pi_Audio/scripts/mpk_isolation_checklist.sh

set -euo pipefail

echo "=========================================="
echo "MPK mini IV — isolation checklist"
echo "=========================================="
echo ""

echo "---- A. Automated (this Pi) ----"
echo ""

echo "[A1] USB: expect vendor 09e8:005d"
if lsusb -d 09e8:005d 2>/dev/null; then
  echo "     PASS: MPK seen on USB."
else
  echo "     FAIL: MPK not in lsusb. Reseat USB, try data cable, direct Pi port."
  exit 1
fi
echo ""

echo "[A2] Kernel: recent lines mentioning MPK / errors (if empty, often OK)"
dmesg 2>/dev/null | grep -iE '09e8|mpk mini|akai' | tail -15 || true
echo ""

echo "[A3] ALSA: MPK client"
aconnect -l | grep -A6 "MPK" || echo "     (no MPK in aconnect — unplug/replug MPK)"
echo ""

echo "---- B. You do (in order) ----"
echo ""
echo " B1) CONFIRM THE PROBE TEST"
echo "     Run (then play KEYS + PADS steadily for the full time, not only knobs):"
echo "       /home/uzan/Raspberri_Pi_Audio/.venv/bin/python /home/uzan/Raspberri_Pi_Audio/midi_key_port_probe.py --seconds 25"
echo "     Expect non-zero counts on at least one line. All zeros = no MIDI reached ALSA."
echo ""
echo " B2) USB PHYSICAL"
echo "     - Pi USB port directly (avoid charge-only cable / bad hub)."
echo "     - During test:  lsusb -d 09e8:005d   should still show the device."
echo ""
echo " B3) PRESET / EDITOR (not on Pi)"
echo "     - Load a User preset (Shift + Plugin/DAW → User Presets), not only DAW/Plugin."
echo "     - Akai MPK mini IV Editor: ensure keybed sends MIDI to USB; no routing that blocks output."
echo "     - akaipro.com → firmware update for MPK mini IV if available."
echo ""
echo " B4) ANOTHER COMPUTER"
echo "     - Plug MPK into PC/Mac → MIDI monitor or DAW MIDI-in meter."
echo "     - If NO notes there either → likely hardware/firmware/service."
echo "     - If notes OK on PC/Mac but not Pi → Pi/USB stack (rare); compare dmesg, try different Pi USB port."
echo ""

echo "---- C. Reference ----"
echo "  midi_connection_check.sh  — USB + ALSA listing"
echo "  midi_listen_test.py       — RtMidi only"
echo "  midi_listen_test.py --amidi-software  — raw Software port"
echo ""
