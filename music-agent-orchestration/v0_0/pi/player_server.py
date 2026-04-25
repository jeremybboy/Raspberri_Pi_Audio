"""V0.0 Pi HTTP player: FastAPI + mpv + OLED status."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import oled_status

log = logging.getLogger(__name__)

app = FastAPI(title="music-agent-v0_0-pi-player", version="0.1.0")

_lock = threading.Lock()
_mpv: subprocess.Popen[Any] | None = None
_last_title: str = ""


def _manifest_path() -> Path:
    env = os.environ.get("MANIFEST_PATH", "").strip()
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parent.parent / "manifest.json"


def _media_root() -> Path:
    env = os.environ.get("MEDIA_ROOT", "").strip()
    if env:
        return Path(env).expanduser()
    return Path("~/music-agent/media").expanduser()


def resolve_audio_path(entry: dict[str, Any], media_root: Path) -> Path:
    """Use path_on_pi when set; else MEDIA_ROOT / filename."""
    raw = entry.get("path_on_pi")
    if raw is not None and str(raw).strip():
        return Path(str(raw).strip()).expanduser()
    fn = entry.get("filename")
    if fn is not None and str(fn).strip():
        return (media_root / str(fn).strip()).resolve()
    raise ValueError("Track entry needs non-empty path_on_pi or filename")


def load_track_index() -> dict[str, dict[str, Any]]:
    mp = _manifest_path()
    if not mp.is_file():
        return {}
    data = json.loads(mp.read_text(encoding="utf-8"))
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
    mp = _manifest_path()
    idx = load_track_index()
    return {
        "ok": True,
        "manifest_path": str(mp.resolve()),
        "manifest_exists": mp.is_file(),
        "track_count": len(idx),
    }


@app.post("/play")
def play(body: PlayBody) -> dict[str, Any]:
    global _mpv, _last_title
    idx = load_track_index()
    if body.track_id not in idx:
        raise HTTPException(status_code=404, detail=f"Unknown track_id: {body.track_id!r}")
    entry = idx[body.track_id]
    try:
        path = resolve_audio_path(entry, _media_root())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"File missing for {body.track_id}: {path}",
        )
    title = str(entry.get("title") or body.track_id).strip() or body.track_id
    _last_title = title
    oled_status.show_status(title, "PLAYING")

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
    oled_status.show_status(_last_title or "—", "STOPPED")
    return {"ok": True}
