#!/usr/bin/env bash
# Layer 2 helper: curl localhost player (P1–P4). Confirm audio/OLED yourself.
set -euo pipefail
BASE="${PI_URL:-http://127.0.0.1:8765}"
echo "GET $BASE/health"
curl -sS "$BASE/health"
echo
read -r -p "track_id to play: " tid
echo "POST $BASE/play track_id=$tid"
curl -sS -X POST "$BASE/play" -H 'Content-Type: application/json' -d "{\"track_id\": \"$tid\"}"
echo
read -r -p "Press Enter when you have checked audio + OLED, then stop..."
echo "POST $BASE/stop"
curl -sS -X POST "$BASE/stop"
echo
