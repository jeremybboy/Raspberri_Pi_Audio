"""V0.1 Pi HTTP player: FastAPI + mpv + OLED meter + landing page."""

from __future__ import annotations

import html
import json
import logging
import os
import socket
import subprocess
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import mpv_ipc, oled_meter, oled_status

log = logging.getLogger(__name__)


def _host_label() -> str:
    h = socket.gethostname().strip() or "pi"
    return h[:21]


def _playback_meter_enabled() -> bool:
    v = os.environ.get("DISABLE_PLAYBACK_METER", "").strip().lower()
    if v in ("1", "true", "yes"):
        return False
    return True


@asynccontextmanager
async def lifespan(_app: FastAPI):
    oled_status.show_status(_host_label(), "v0_1 READY")
    yield
    _stop_meter_thread()
    oled_status.show_status(_host_label(), "server off")


app = FastAPI(
    title="music-agent-v0_1-pi-player",
    version="0.2.0",
    lifespan=lifespan,
)


_lock = threading.Lock()
_mpv: subprocess.Popen[Any] | None = None
_last_title: str = ""
_ipc_sock_path: str | None = None
_meter_stop = threading.Event()
_meter_thread: threading.Thread | None = None


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


def load_tracks_ordered() -> list[dict[str, Any]]:
    mp = _manifest_path()
    if not mp.is_file():
        return []
    data = json.loads(mp.read_text(encoding="utf-8"))
    return list(data.get("tracks", []))


def _stop_meter_thread() -> None:
    global _meter_thread, _ipc_sock_path
    _meter_stop.set()
    if _meter_thread is not None:
        _meter_thread.join(timeout=2.5)
        _meter_thread = None
    if _ipc_sock_path and os.path.exists(_ipc_sock_path):
        try:
            os.unlink(_ipc_sock_path)
        except OSError:
            pass
    _ipc_sock_path = None


def _meter_loop(sock_path: str, title: str) -> None:
    tick = 0
    while not _meter_stop.is_set():
        if _mpv is None or _mpv.poll() is not None:
            break
        pct = mpv_ipc.get_percent_pos(sock_path)
        oled_meter.show_playback_bar(title, pct, tick)
        tick += 1
        time.sleep(0.18)
    _meter_stop.clear()


def _build_landing_html() -> str:
    tracks = load_tracks_ordered()
    rows = []
    for t in tracks:
        tid = html.escape(str(t.get("id", "")))
        ttl = html.escape(str(t.get("title", tid)))
        rows.append(
            f'<div class="row"><button type="button" data-tid="{tid}">Play: {ttl}</button></div>'
        )
    tracks_html = "\n".join(rows) if rows else "<p>No tracks in manifest.</p>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Music Agent Player</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 42rem; margin: 1.5rem auto; padding: 0 1rem; }}
    h1 {{ font-size: 1.35rem; }}
    ul {{ line-height: 1.5; }}
    .row {{ margin: 0.35rem 0; }}
    button {{ cursor: pointer; padding: 0.35rem 0.6rem; }}
    #status {{ margin-top: 1rem; font-size: 0.9rem; color: #333; }}
    a {{ color: #06c; }}
  </style>
</head>
<body>
  <h1>Music Agent Player</h1>
  <p>This Pi plays songs from your manifest over USB audio. Use the buttons below or the API (<a href="/docs">OpenAPI / Swagger</a>).</p>
  <p><strong>Future skills</strong> (not implemented here):</p>
  <ul>
    <li>Source separation (stems)</li>
    <li>Remix / style transfer</li>
    <li>Catalog sync from cloud storage</li>
  </ul>
  <h2>Tracks</h2>
  {tracks_html}
  <p><button type="button" id="stopbtn">Stop</button></p>
  <p id="status"></p>
  <script>
    function setStatus(msg) {{
      document.getElementById('status').textContent = msg;
    }}
    async function postPlay(tid) {{
      setStatus('Playing…');
      const r = await fetch('/play', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ track_id: tid }})
      }});
      const j = await r.json().catch(() => ({{}}));
      if (!r.ok) setStatus('Error: ' + (j.detail || r.status));
      else setStatus('OK: ' + tid);
    }}
    async function postStop() {{
      setStatus('Stopping…');
      const r = await fetch('/stop', {{ method: 'POST' }});
      const j = await r.json().catch(() => ({{}}));
      if (!r.ok) setStatus('Error: ' + (j.detail || r.status));
      else setStatus('Stopped.');
    }}
    document.querySelectorAll('button[data-tid]').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        postPlay(btn.getAttribute('data-tid'));
      }});
    }});
    document.getElementById('stopbtn').addEventListener('click', postStop);
  </script>
</body>
</html>
"""


@app.get("/", include_in_schema=False)
def root() -> HTMLResponse:
    return HTMLResponse(content=_build_landing_html())


@app.get("/api/tracks")
def api_tracks() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for t in load_tracks_ordered():
        tid = str(t.get("id", "")).strip()
        if not tid:
            continue
        title = str(t.get("title") or tid).strip()
        out.append({"id": tid, "title": title})
    return out


def _stop_unlocked() -> None:
    global _mpv
    _stop_meter_thread()
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
def health(
    oled: bool = Query(
        False,
        description="If true, refresh OLED with host + idle/manifest snapshot.",
    ),
) -> dict[str, Any]:
    mp = _manifest_path()
    idx = load_track_index()
    if oled:
        if not mp.is_file():
            oled_status.show_status(_host_label(), "!no manifest")
        else:
            oled_status.show_status(_host_label(), f"idle {len(idx)} trk"[:16])
    return {
        "ok": True,
        "manifest_path": str(mp.resolve()),
        "manifest_exists": mp.is_file(),
        "track_count": len(idx),
    }


@app.post("/play")
def play(body: PlayBody) -> dict[str, Any]:
    global _mpv, _last_title, _meter_thread, _ipc_sock_path
    idx = load_track_index()
    if body.track_id not in idx:
        tid = body.track_id[:14] + ("..." if len(body.track_id) > 14 else "")
        oled_status.show_status(f">{tid}", "404 NO TRACK"[:16])
        raise HTTPException(status_code=404, detail=f"Unknown track_id: {body.track_id!r}")
    entry = idx[body.track_id]
    try:
        path = resolve_audio_path(entry, _media_root())
    except ValueError as e:
        oled_status.show_status(_host_label(), "BAD ENTRY"[:16])
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not path.is_file():
        oled_status.show_status(body.track_id[:16], "MISSING FILE"[:16])
        raise HTTPException(
            status_code=400,
            detail=f"File missing for {body.track_id}: {path}",
        )
    title = str(entry.get("title") or body.track_id).strip() or body.track_id
    _last_title = title

    mpv_bin = os.environ.get("MPV_BIN", "mpv")
    extra = os.environ.get("MPV_OPTS", "").strip()

    sock = f"/tmp/music-agent-v01-{os.getpid()}-{threading.get_ident()}.sock"
    try:
        if os.path.exists(sock):
            os.unlink(sock)
    except OSError:
        pass

    cmd = [mpv_bin, "--no-video", str(path)]
    if _playback_meter_enabled():
        cmd.append(f"--input-ipc-server={sock}")
    if extra:
        cmd.extend(extra.split())

    with _lock:
        _stop_unlocked()
        oled_status.show_status(title, "PLAYING")
        _mpv = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        if _playback_meter_enabled():
            _ipc_sock_path = sock
            _meter_stop.clear()
            # Wait for mpv to create the IPC socket
            for _ in range(40):
                if os.path.exists(sock):
                    break
                time.sleep(0.025)
            _meter_thread = threading.Thread(
                target=_meter_loop,
                args=(sock, title),
                daemon=True,
                name="oled-meter",
            )
            _meter_thread.start()

    return {"ok": True, "track_id": body.track_id, "path": str(path.resolve())}


@app.post("/stop")
def stop() -> dict[str, bool]:
    with _lock:
        _stop_unlocked()
    oled_status.show_status(_last_title or "—", "STOPPED")
    return {"ok": True}
