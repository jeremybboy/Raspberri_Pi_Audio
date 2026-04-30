"""V0.2 Pi HTTP player: FastAPI + Lambda presign + mpv + OLED meter."""

from __future__ import annotations

import html
import logging
import os
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import mpv_ipc, oled_meter, oled_status

log = logging.getLogger(__name__)
_OLED_BOOT_HANDOFF_FILE = "/tmp/music-agent-v02-oled.handoff"


def _host_label() -> str:
    h = socket.gethostname().strip() or "pi"
    return h[:21]


def _playback_meter_enabled() -> bool:
    v = os.environ.get("DISABLE_PLAYBACK_METER", "").strip().lower()
    if v in ("1", "true", "yes"):
        return False
    return True


def _meter_mode() -> str:
    mode = os.environ.get("PLAYBACK_METER_MODE", "ffmpeg").strip().lower()
    if mode in ("ffmpeg", "none"):
        return mode
    return "ffmpeg"


def _oled_refresh_seconds() -> float:
    raw = os.environ.get("OLED_REFRESH_SECONDS", "").strip()
    try:
        value = float(raw) if raw else 0.08
    except ValueError:
        return 0.08
    return max(0.03, min(0.5, value))


def _db_probe_interval_seconds() -> float:
    raw = os.environ.get("DB_PROBE_INTERVAL_SECONDS", "").strip()
    try:
        value = float(raw) if raw else 0.35
    except ValueError:
        return 0.35
    return max(0.1, min(2.0, value))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Stop the boot/status rotator while this server owns the OLED.
    try:
        with open(_OLED_BOOT_HANDOFF_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass
    oled_status.show_status(_host_label(), "v0_2 READY")
    try:
        yield
    finally:
        _stop_meter_thread()
        oled_status.show_status(_host_label(), "server off")
        try:
            if os.path.exists(_OLED_BOOT_HANDOFF_FILE):
                os.unlink(_OLED_BOOT_HANDOFF_FILE)
        except OSError:
            pass


app = FastAPI(
    title="music-agent-v0_2-pi-player",
    version="0.3.0",
    lifespan=lifespan,
)


_lock = threading.Lock()
_mpv: subprocess.Popen[Any] | None = None
_last_title: str = ""
_ipc_sock_path: str | None = None
_meter_stop = threading.Event()
_meter_thread: threading.Thread | None = None
_tracks_cache: list[dict[str, str]] = []
_tracks_cache_at = 0.0


def _lambda_base_url() -> str:
    return os.environ.get("LAMBDA_FUNCTION_URL", "").strip()


def _cloud_api_key() -> str:
    return os.environ.get("CLOUD_API_KEY", "").strip()


def _tracks_cache_ttl_seconds() -> float:
    raw = os.environ.get("TRACKS_CACHE_TTL_SECONDS", "").strip()
    try:
        value = float(raw) if raw else 45.0
    except ValueError:
        return 45.0
    return max(0.0, min(300.0, value))


def _http_timeout_seconds() -> float:
    raw = os.environ.get("CLOUD_HTTP_TIMEOUT_SECONDS", "").strip()
    try:
        value = float(raw) if raw else 8.0
    except ValueError:
        return 8.0
    return max(1.0, min(20.0, value))


def _debug_full_url() -> bool:
    v = os.environ.get("V0_2_DEBUG_FULL_URL", "").strip().lower()
    return v in ("1", "true", "yes")


@dataclass
class CloudPlay:
    track_id: str
    title: str
    presigned_url: str
    expires_in: int | None
    lambda_host: str


def _lambda_headers() -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    key = _cloud_api_key()
    if key:
        headers["X-Api-Key"] = key
    return headers


def _require_lambda_config() -> str:
    base = _lambda_base_url()
    if not base:
        raise HTTPException(
            status_code=500,
            detail="LAMBDA_FUNCTION_URL is not configured",
        )
    return base.rstrip("/")


def _url_preview(url: str) -> str:
    if _debug_full_url():
        return url
    if len(url) <= 48:
        return url
    return f"{url[:20]}...{url[-20:]}"


def _cloud_host() -> str:
    base = _lambda_base_url()
    if not base:
        return ""
    try:
        return httpx.URL(base).host or ""
    except Exception:
        return ""


def _fetch_tracks_from_cloud(force: bool = False) -> list[dict[str, str]]:
    global _tracks_cache, _tracks_cache_at
    if not force:
        ttl = _tracks_cache_ttl_seconds()
        now = time.monotonic()
        if ttl > 0 and _tracks_cache and (now - _tracks_cache_at) < ttl:
            return list(_tracks_cache)

    base = _require_lambda_config()
    endpoint = f"{base}/tracks"
    try:
        r = httpx.get(
            endpoint,
            headers=_lambda_headers(),
            timeout=_http_timeout_seconds(),
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Cloud tracks fetch failed: {e}") from e
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Cloud tracks fetch failed: {r.status_code}")
    body = r.json()
    rows: list[Any]
    if isinstance(body, list):
        rows = body
    elif isinstance(body, dict) and isinstance(body.get("tracks"), list):
        rows = body["tracks"]
    else:
        raise HTTPException(
            status_code=502,
            detail="Cloud tracks response must be a JSON list or object with tracks[]",
        )

    out: list[dict[str, str]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id") or item.get("track_id") or "").strip()
        if not tid:
            continue
        title = str(item.get("title") or tid).strip() or tid
        out.append({"id": tid, "title": title})
    _tracks_cache = out
    _tracks_cache_at = time.monotonic()
    return list(out)


def _request_cloud_play(track_id: str) -> CloudPlay:
    base = _require_lambda_config()
    endpoint = f"{base}/play"
    payload = {"track_id": track_id}
    try:
        r = httpx.post(
            endpoint,
            headers=_lambda_headers(),
            json=payload,
            timeout=_http_timeout_seconds(),
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Cloud play request failed: {e}") from e

    if r.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Unknown track_id: {track_id!r}")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Cloud play request failed: {r.status_code}")

    body = r.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=502, detail="Cloud play response must be a JSON object")

    presigned_url = str(body.get("presigned_url") or "").strip()
    if not presigned_url:
        raise HTTPException(status_code=502, detail="Cloud play response missing presigned_url")
    title = str(body.get("title") or track_id).strip() or track_id
    expires_raw = body.get("expires_in")
    expires_in = int(expires_raw) if isinstance(expires_raw, (int, float)) else None
    lambda_host = httpx.URL(base).host or ""
    return CloudPlay(
        track_id=track_id,
        title=title,
        presigned_url=presigned_url,
        expires_in=expires_in,
        lambda_host=lambda_host,
    )


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


def _meter_loop(sock_path: str, title: str, audio_path: str) -> None:
    tick = 0
    db_value: float | None = None
    last_db_at = 0.0
    refresh_s = _oled_refresh_seconds()
    db_interval_s = _db_probe_interval_seconds()
    while not _meter_stop.is_set():
        if _mpv is None or _mpv.poll() is not None:
            break
        time_pos = mpv_ipc.get_time_pos(sock_path)
        duration = mpv_ipc.get_duration(sock_path)

        # ffmpeg probing is heavier, so sample at a lower cadence.
        now = time.monotonic()
        if _meter_mode() == "ffmpeg" and (now - last_db_at) >= db_interval_s:
            db_value = oled_meter.estimate_db_window(audio_path, time_pos)
            last_db_at = now

        oled_meter.show_playback_vu(title, time_pos, duration, db_value, tick)
        tick += 1
        time.sleep(refresh_s)
    _meter_stop.clear()


def _build_landing_html() -> str:
    tracks = _fetch_tracks_from_cloud()
    rows = []
    for t in tracks:
        tid = html.escape(str(t.get("id", "")))
        ttl = html.escape(str(t.get("title", tid)))
        rows.append(
            f'<div class="row"><button type="button" data-tid="{tid}">Play: {ttl}</button></div>'
        )
    tracks_html = "\n".join(rows) if rows else "<p>No tracks in cloud catalog.</p>"
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
    .flow-box {{ margin-top: 1rem; border: 1px solid #ddd; border-radius: 8px; padding: 0.75rem; background: #fafafa; }}
    .flow-title {{ margin: 0 0 0.5rem; font-size: 1rem; }}
    .flow-note {{ margin: 0.35rem 0 0.6rem; color: #444; font-size: 0.9rem; }}
    .flow-row {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; }}
    .flow-step {{
      border: 1px solid #bbb;
      border-radius: 6px;
      background: #fff;
      padding: 0.35rem 0.5rem;
      font-size: 0.82rem;
      transition: all 0.18s ease;
      opacity: 0.75;
    }}
    .flow-arrow {{ color: #666; font-size: 0.85rem; }}
    .flow-step.active {{
      border-color: #0a66d8;
      background: #eaf3ff;
      color: #0a66d8;
      opacity: 1;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <h1>Music Agent Player</h1>
  <p>This Pi plays songs from cloud catalog via Lambda presign + S3 over HTTPS. Use buttons below or API (<a href="/docs">OpenAPI / Swagger</a>).</p>
  <p><strong>Future skills</strong> (not implemented here):</p>
  <ul>
    <li>Source separation (stems)</li>
    <li>Remix / style transfer</li>
    <li>Catalog sync from cloud storage</li>
  </ul>
  <h2>Tracks</h2>
  {tracks_html}
  <p><button type="button" id="stopbtn">Stop</button></p>
  <div class="flow-box">
    <h3 class="flow-title">How Play Works</h3>
    <p class="flow-note">Click Play to highlight each step in the request flow.</p>
    <div class="flow-row">
      <div class="flow-step" id="step-browser">Browser click</div>
      <div class="flow-arrow">→</div>
      <div class="flow-step" id="step-pi">Pi /play API</div>
      <div class="flow-arrow">→</div>
      <div class="flow-step" id="step-lambda">Lambda /play</div>
      <div class="flow-arrow">→</div>
      <div class="flow-step" id="step-signed">Signed S3 URL</div>
      <div class="flow-arrow">→</div>
      <div class="flow-step" id="step-mpv">mpv on Pi</div>
    </div>
  </div>
  <p id="status"></p>
  <script>
    function clearFlow() {{
      ['step-browser', 'step-pi', 'step-lambda', 'step-signed', 'step-mpv'].forEach(function(id) {{
        const el = document.getElementById(id);
        if (el) el.classList.remove('active');
      }});
    }}
    function activateStep(id) {{
      const el = document.getElementById(id);
      if (el) el.classList.add('active');
    }}
    function setStatus(lines) {{
      const value = Array.isArray(lines) ? lines.join('\\n') : String(lines);
      document.getElementById('status').textContent = value;
    }}
    async function postPlay(tid) {{
      clearFlow();
      activateStep('step-browser');
      activateStep('step-pi');
      setStatus(['Calling Pi /play...', 'Waiting for Lambda presign...']);
      const r = await fetch('/play', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ track_id: tid }})
      }});
      const j = await r.json().catch(() => ({{}}));
      if (!r.ok) {{
        setStatus('Error: ' + (j.detail || r.status));
      }} else {{
        activateStep('step-lambda');
        activateStep('step-signed');
        activateStep('step-mpv');
        const lines = [];
        lines.push('OK: ' + tid);
        if (Array.isArray(j.trace)) lines.push(...j.trace);
        if (j.cloud && j.cloud.url_preview) lines.push('URL: ' + j.cloud.url_preview);
        setStatus(lines);
      }}
    }}
    async function postStop() {{
      setStatus('Stopping…');
      const r = await fetch('/stop', {{ method: 'POST' }});
      const j = await r.json().catch(() => ({{}}));
      if (!r.ok) setStatus('Error: ' + (j.detail || r.status));
      else {{
        setStatus('Stopped.');
        clearFlow();
      }}
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
    return _fetch_tracks_from_cloud()


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
    track_count = 0
    cloud_error = ""
    try:
        track_count = len(_fetch_tracks_from_cloud())
    except HTTPException as e:
        cloud_error = str(e.detail)
    if oled:
        label = f"idle {track_count} trk"
        if cloud_error:
            label = "cloud err"
        oled_status.show_status(_host_label(), label[:16])
    return {
        "ok": True,
        "version": "v0_2",
        "track_count": track_count,
        "lambda_configured": bool(_lambda_base_url()),
        "lambda_host": _cloud_host(),
        "cloud_error": cloud_error,
        "playback_meter_mode": _meter_mode(),
    }


@app.post("/play")
def play(body: PlayBody) -> dict[str, Any]:
    global _mpv, _last_title, _meter_thread, _ipc_sock_path
    trace = [f"Request track_id={body.track_id}", "Calling Lambda /play..."]
    cloud_play = _request_cloud_play(body.track_id)
    trace.append("Lambda presign received")
    title = cloud_play.title
    _last_title = title

    mpv_bin = os.environ.get("MPV_BIN", "mpv")
    extra = os.environ.get("MPV_OPTS", "").strip()

    sock = f"/tmp/music-agent-v02-{os.getpid()}-{threading.get_ident()}.sock"
    try:
        if os.path.exists(sock):
            os.unlink(sock)
    except OSError:
        pass

    cmd = [mpv_bin, "--no-video", cloud_play.presigned_url]
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
                args=(sock, title, cloud_play.presigned_url),
                daemon=True,
                name="oled-meter",
            )
            _meter_thread.start()

    trace.append("Starting mpv with presigned URL")
    return {
        "ok": True,
        "track_id": body.track_id,
        "title": title,
        "trace": trace,
        "cloud": {
            "lambda_host": cloud_play.lambda_host,
            "expires_in": cloud_play.expires_in,
            "url_preview": _url_preview(cloud_play.presigned_url),
        },
    }


@app.post("/stop")
def stop() -> dict[str, bool]:
    with _lock:
        _stop_unlocked()
    oled_status.show_status(_last_title or "—", "STOPPED")
    return {"ok": True}
