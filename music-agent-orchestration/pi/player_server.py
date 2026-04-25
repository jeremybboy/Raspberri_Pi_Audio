"""Minimal HTTP player API for Raspberry Pi: play/stop via mpv + ALSA."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="music-agent-pi-player", version="0.1.0")

_lock = threading.Lock()
_mpv: subprocess.Popen[Any] | None = None


def _default_manifest_path() -> Path:
    env = os.environ.get("MANIFEST_PATH", "").strip()
    if env:
        return Path(env).expanduser()
    # music-agent-orchestration/manifest.json when package is pi/
    return Path(__file__).resolve().parent.parent / "manifest.json"


MANIFEST_PATH: Path = _default_manifest_path()


def load_track_index() -> dict[str, dict[str, Any]]:
    if not MANIFEST_PATH.is_file():
        return {}
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    tracks = data.get("tracks", [])
    return {str(t["id"]): t for t in tracks if "id" in t}


def _stop_unlocked() -> None:
    global _mpv
    if _mpv is None:
        return
    if _mpv.poll() is None:
        _mpv.terminate()
        try:
            _mpv.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            _mpv.kill()
            _mpv.wait(timeout=2.0)
    _mpv = None


class PlayBody(BaseModel):
    track_id: str = Field(..., min_length=1)


@app.get("/health")
def health() -> dict[str, Any]:
    idx = load_track_index()
    return {
        "ok": True,
        "manifest_path": str(MANIFEST_PATH.resolve()),
        "manifest_exists": MANIFEST_PATH.is_file(),
        "track_count": len(idx),
    }


@app.post("/play")
def play(body: PlayBody) -> dict[str, Any]:
    global _mpv
    idx = load_track_index()
    if body.track_id not in idx:
        raise HTTPException(status_code=404, detail=f"Unknown track_id: {body.track_id!r}")
    entry = idx[body.track_id]
    path = Path(entry["path_on_pi"])
    if not path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"File missing for {body.track_id}: {path}",
        )
    mpv_bin = os.environ.get("MPV_BIN", "mpv")
    extra = os.environ.get("MPV_OPTS", "").strip()
    cmd = [mpv_bin, "--no-video", str(path)]
    if extra:
        cmd.extend(extra.split())
    with _lock:
        _stop_unlocked()
        _mpv = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    return {"ok": True, "track_id": body.track_id, "path": str(path.resolve())}


@app.post("/stop")
def stop() -> dict[str, bool]:
    with _lock:
        _stop_unlocked()
    return {"ok": True}
