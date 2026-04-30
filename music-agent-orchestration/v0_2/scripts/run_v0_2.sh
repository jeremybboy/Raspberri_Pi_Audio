#!/usr/bin/env bash
# Load local secrets from .env.local (if present) and start v0_2.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f ".env.local" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env.local"
  set +a
fi

exec python -m uvicorn pi.player_server:app --host 0.0.0.0 --port "${PORT:-8767}"
