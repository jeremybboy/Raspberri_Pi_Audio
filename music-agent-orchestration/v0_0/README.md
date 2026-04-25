# Music agent orchestration — V0.0 (simplified)

Self-contained workspace under `music-agent-orchestration/v0_0/`. **Do not modify** the parent folder’s Ollama/Dropbox-oriented `mac/` and `pi/` while you prove this line; add code here (`v0_0/pi/`, optional `v0_0/mac/` or shell scripts) instead.

---

## Goal

Build a **minimal, reliable** end-to-end system where a **Mac** (control plane) sends a command to a **Raspberry Pi** (playback device), and the Pi **plays audio** through its audio interface and **shows status on an OLED**.

This is **V0.0** (deliberately simplified).

### Explicitly out of scope (do not add yet)

- Dropbox API / cloud sync  
- Streaming  
- LLM-based track selection  
- Complex configs  

### In scope (only this)

Validate: **Mac → command → Pi → audio plays + OLED updates**

---

## Architecture

| Role | Responsibility |
|------|----------------|
| **Mac (controller)** | Sends HTTP commands; holds a local manifest (`track_id` → metadata). |
| **Raspberry Pi (player)** | HTTP server; plays audio via **mpv**; output via **Behringer USB**; **OLED** status. |

---

## Step 1 — Network and access

- Mac and Pi on the same LAN  
- SSH from Mac → Pi works  
- Stable Pi IP or hostname  

**Success:** SSH into the Pi from the Mac.

---

## Step 2 — Audio files on Pi

- Pick **2–5** test audio files  
- Copy Mac → Pi (`scp` or `rsync`)  
- Fixed directory, e.g. `~/music-agent/media/`  

**Success:** Files on Pi; manual check: `mpv /path/to/file.mp3`

---

## Step 3 — Manifest (shared contract)

Same **shape** on **both** Mac and Pi. Example: see `manifest.example.json` in this folder.

**Critical rule**

- `track_id` (field `id` in JSON) **must match** on Mac and Pi.  
- This is the **only** contract between systems.

**Failure mode:** ID mismatch → nothing plays.

**Path resolution on Pi**

```text
path_on_pi = ~/music-agent/media/<filename>
```

(Implement your player to resolve `filename` relative to a configurable media root if you prefer.)

---

## Step 4 — Pi player server (core)

Small HTTP server (**FastAPI** or **Flask**) on the Pi.

| Method | Path | Behavior |
|--------|------|----------|
| `GET` | `/health` | Returns OK (and optional manifest stats). |
| `POST` | `/play` | Body: `{ "track_id": "track_1" }` — lookup manifest, resolve file, run **mpv**, update **OLED** (title + **PLAYING**). |
| `POST` | `/stop` | Stop playback; OLED **STOPPED**. |

**Dependencies:** `mpv`, Python web stack, OLED library (e.g. `luma.oled` as in the main Pi repo).

**Success:** `curl` `POST /play` → sound + OLED update.

**Suggested default port:** `8765` (document in your run command).

---

## Step 5 — Mac control (client)

From Mac:

```http
POST http://<pi-ip>:8765/play
Content-Type: application/json

{ "track_id": "track_1" }
```

```http
POST http://<pi-ip>:8765/stop
```

No UI required — `curl` or a tiny CLI is enough.

**Success:** Mac triggers playback remotely.

---

## OLED (required, not decorative)

Minimum:

- Track title  
- State: **PLAYING** / **STOPPED**  

Purpose: debugging and UX.

---

## Audio output

- Playback **only** on the Pi  
- **Behringer USB** (or documented ALSA device) — **not** through the Mac speakers  

---

## After V0.0 (not now)

Only after the definition of done passes:

- LLM track selection  
- Dropbox  
- Streaming / download-on-demand  
- Caching  

---

## Definition of done (V0.0)

1. Server runs on Pi  
2. Play request from Mac  
3. Audio heard on Pi (USB path)  
4. OLED shows correct title + state  
5. Stop works from Mac  

If any step fails → **not done**.

---

## Philosophy

- Remove complexity  
- Validate control flow  
- Prove reliability  
- **No feature creep** until stable  

---

## Layout

```text
v0_0/
  README.md
  manifest.example.json
  requirements-pi.txt
  requirements-dev.txt
  scripts/smoke_v0_0.sh
  scripts/oled_hello.py
  scripts/oled_live_status.py
  mac/pi_player.sh
  pi/
    player_server.py
    oled_status.py
    tests/
```

Parent repo reference for OLED/audio patterns: `../../` (e.g. `oled_linein_level_meter.py`, venv at repo root).

---

## Run on the Pi

**Python:** Either use the repo root [`.venv`](../../.venv) (already includes `luma.oled` and can add FastAPI with `pip install -r music-agent-orchestration/v0_0/requirements-pi.txt`) or create `music-agent-orchestration/v0_0/.venv` and install from [`requirements-pi.txt`](requirements-pi.txt).

**System:** `mpv` installed; I2C enabled for the OLED.

**Paths:** Put audio under `~/music-agent/media/` (or set `MEDIA_ROOT`). Copy [`manifest.example.json`](manifest.example.json) to `music-agent-orchestration/v0_0/manifest.json` and adjust `id` / `title` / `filename` (or use `path_on_pi` — that wins over `filename` when both are set).

**Environment (optional):**

| Variable | Meaning |
|----------|---------|
| `MANIFEST_PATH` | Default: `v0_0/manifest.json` next to this README’s folder |
| `MEDIA_ROOT` | Default: `~/music-agent/media` |
| `MPV_BIN` | Default: `mpv` |
| `MPV_OPTS` | Extra args (e.g. ALSA device). Discover names on the Pi: `aplay -L` / `aplay -l` |
| `DISABLE_OLED` | Set to `1` for headless / tests (no hardware) |
| `I2C_PORT` | Default `1` |
| `I2C_ADDR` | Default `0x3C` |

**Start the server** (from repo root, default port **8765**):

```bash
cd /path/to/Raspberri_Pi_Audio/music-agent-orchestration/v0_0
/path/to/.venv/bin/python -m uvicorn pi.player_server:app --host 0.0.0.0 --port 8765
```

### Dynamic OLED feedback (“where we are”)

- **On server start / stop:** the OLED shows **hostname** + `v0_0 READY`, then **server off** when uvicorn exits.
- **While the server runs:** `GET /health?oled=1` pushes **hostname** + an **idle** line (`idle N trk`, or `!no manifest`). Use this from the Mac whenever you want the display to reflect a ping.
- **Play / stop:** unchanged — track title + **PLAYING**; last title + **STOPPED**. Failed **play** updates the OLED briefly (`404 NO TRACK`, `MISSING FILE`, etc.).
- **Continuous mirror (second terminal on the Pi):** polls `/health` every 2s and draws **hostname** + `OK Ntr mf=1` (or `NO SERVER` if down). Ctrl+C shows `live off`.

```bash
# Terminal A: uvicorn (as above)
# Terminal B on the Pi:
cd /path/to/Raspberri_Pi_Audio/music-agent-orchestration/v0_0
/path/to/.venv/bin/python scripts/oled_live_status.py
# Optional: PI_URL=http://127.0.0.1:8765 OLED_POLL_SEC=1.5
```

From the Mac (interactive ping + OLED refresh):

```bash
curl -sS "http://<pi-ip>:8765/health?oled=1"
```

---

## Testing

### Layer 1 — Automated (pytest)

From `music-agent-orchestration/v0_0` (repo clone):

```bash
cd music-agent-orchestration/v0_0
/path/to/.venv/bin/pip install -r requirements-dev.txt
/path/to/.venv/bin/python -m pytest pi/tests -q
```

Uses `DISABLE_OLED` via `conftest.py`; mocks `mpv` where needed.

### Layer 2 — Pi-local smoke

With the server listening on `127.0.0.1:8765`, use `curl` or:

```bash
bash scripts/smoke_v0_0.sh
```

You still confirm **audio** and **OLED** manually (P2–P5 in the implementation plan).

### Layer 3 — End-to-end checklist (Mac → Pi)

Prereq: Pi running uvicorn on `0.0.0.0:8765`, Mac on same LAN, TCP 8765 allowed.

```bash
export PI=http://<pi-ip>:8765

curl -sS "$PI/health"
echo

curl -sS -X POST "$PI/play" -H 'Content-Type: application/json' \
  -d '{"track_id":"<valid_id_from_manifest>"}'
echo

# Listen on the Pi speakers/headphones; check OLED: title + PLAYING

curl -sS -X POST "$PI/stop"
echo

# OLED should show STOPPED

curl -sS -X POST "$PI/play" -H 'Content-Type: application/json' \
  -d '{"track_id":"nonexistent"}'
echo
# Expect 404
```

Optional Mac helper ([`mac/pi_player.sh`](mac/pi_player.sh)):

```bash
export PI_BASE_URL=http://<pi-ip>:8765
bash mac/pi_player.sh health
bash mac/pi_player.sh play '<valid_id>'
bash mac/pi_player.sh stop
```
