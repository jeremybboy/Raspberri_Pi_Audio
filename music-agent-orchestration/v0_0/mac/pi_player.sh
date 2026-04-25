#!/usr/bin/env bash
# Optional Mac client: set PI_BASE_URL=http://<pi-ip>:8765
set -euo pipefail
BASE="${PI_BASE_URL:?Set PI_BASE_URL e.g. http://192.168.1.50:8765}"
cmd="${1:-}"
case "$cmd" in
  play)
    tid="${2:?usage: play <track_id>}"
    curl -sS -X POST "$BASE/play" -H 'Content-Type: application/json' -d "{\"track_id\": \"$tid\"}"
    echo
    ;;
  stop)
    curl -sS -X POST "$BASE/stop"
    echo
    ;;
  health)
    curl -sS "$BASE/health"
    echo
    ;;
  *)
    echo "usage: PI_BASE_URL=http://<pi>:8765 $0 health|play <track_id>|stop" >&2
    exit 1
    ;;
esac
