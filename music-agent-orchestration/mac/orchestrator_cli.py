"""CLI: send play/stop to Pi HTTP API; optional Ollama to pick track_id from manifest."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def track_list_for_prompt(data: dict[str, Any]) -> str:
    lines: list[str] = []
    for t in data.get("tracks", []):
        tid = t.get("id", "")
        title = t.get("title", "")
        lines.append(f"- {tid}: {title}")
    return "\n".join(lines) if lines else "(no tracks)"


def pick_track_via_ollama(
    host: str,
    model: str,
    manifest_summary: str,
    user_prompt: str,
) -> str:
    url = f"{host.rstrip('/')}/api/chat"
    system = (
        "You choose exactly one music track from the list. "
        'Reply with a single JSON object only, no markdown: {"track_id":"<id>"} '
        "where <id> is one of the ids from the list."
    )
    user = f"Available tracks:\n{manifest_summary}\n\nUser request:\n{user_prompt}"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        body = r.json()
    msg = body.get("message", {})
    content = msg.get("content", "")
    if not content:
        raise RuntimeError(f"Unexpected Ollama response: {body!r}")
    m = re.search(r"\{[^{}]*\"track_id\"[^{}]*\}", content, re.DOTALL)
    if not m:
        raise RuntimeError(f"Could not parse JSON from model output: {content!r}")
    obj = json.loads(m.group(0))
    tid = obj.get("track_id")
    if not tid or not isinstance(tid, str):
        raise RuntimeError(f"Invalid track_id in model JSON: {obj!r}")
    return tid


def cmd_play(args: argparse.Namespace) -> int:
    pi_base = args.pi_url.rstrip("/")
    manifest_path = Path(args.manifest_path).expanduser()
    data = load_manifest(manifest_path)
    track_ids = {str(t["id"]) for t in data.get("tracks", []) if "id" in t}

    if args.use_ollama:
        if not args.prompt:
            print("--prompt is required with --use-ollama", file=sys.stderr)
            return 2
        summary = track_list_for_prompt(data)
        track_id = pick_track_via_ollama(
            args.ollama_host,
            args.ollama_model,
            summary,
            args.prompt,
        )
        print(f"ollama chose track_id={track_id!r}")
    else:
        if not args.track_id:
            print("Either --track-id or --use-ollama --prompt is required for play", file=sys.stderr)
            return 2
        track_id = args.track_id
        if track_id not in track_ids:
            print(f"Unknown track_id {track_id!r} (not in manifest)", file=sys.stderr)
            return 2

    url = f"{pi_base}/play"
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, json={"track_id": track_id})
        if r.status_code >= 400:
            print(r.text, file=sys.stderr)
            r.raise_for_status()
        print(r.json())
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    pi_base = args.pi_url.rstrip("/")
    url = f"{pi_base}/stop"
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url)
        if r.status_code >= 400:
            print(r.text, file=sys.stderr)
            r.raise_for_status()
        print(r.json())
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    pi_base = args.pi_url.rstrip("/")
    url = f"{pi_base}/health"
    with httpx.Client(timeout=10.0) as client:
        r = client.get(url)
        r.raise_for_status()
        print(r.json())
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Music agent v0 — control Pi player from Mac")
    p.add_argument(
        "--pi-url",
        default=os.environ.get("PI_PLAYER_BASE_URL", "http://127.0.0.1:8765"),
        help="Base URL of Pi player API",
    )
    p.add_argument(
        "--manifest-path",
        type=Path,
        default=Path(os.environ.get("MANIFEST_PATH", "manifest.json")),
        help="Path to manifest.json on this machine",
    )
    p.add_argument(
        "--ollama-host",
        default=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
    )
    p.add_argument(
        "--ollama-model",
        default=os.environ.get("OLLAMA_MODEL", "llama3.2"),
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_play = sub.add_parser("play", help="POST /play on Pi")
    p_play.add_argument("--track-id", help="Explicit track id from manifest")
    p_play.add_argument("--use-ollama", action="store_true", help="Ask Ollama to pick track")
    p_play.add_argument("--prompt", help="Natural language request when using --use-ollama")
    p_play.set_defaults(func=cmd_play)

    p_stop = sub.add_parser("stop", help="POST /stop on Pi")
    p_stop.set_defaults(func=cmd_stop)

    p_health = sub.add_parser("health", help="GET /health on Pi")
    p_health.set_defaults(func=cmd_health)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
