# Music agent orchestration — V0.1

Self-contained workspace under `music-agent-orchestration/v0_1/`. Builds on **[V0.0](../v0_0/)** (same manifest + `mpv` + HTTP contract) with:

- **Landing page** at `/` (“Music Agent Player” + future skills blurb + track buttons).
- **`GET /api/tracks`** — JSON list of `{ id, title }` for scripts or the UI.
- **OLED playback clock + VU meter** — during play, shows title + `mm:ss / total` from **mpv IPC**, plus a separate VU-style dB bar (`ffmpeg` probe by default), unless `DISABLE_PLAYBACK_METER=1`.

**Do not modify** the parent folder’s Ollama/Dropbox-oriented `mac/` and `pi/` at `music-agent-orchestration/` root here; keep orchestration experiments under `v0_1/pi/` and `v0_1/mac/` only.

**Operator cheat sheet:** [OPERATORS.md](OPERATORS.md).

---

## Goal

Same end-to-end story as V0.0: **Mac → HTTP → Pi → USB audio + OLED**, with a clearer **operator UI** and **richer OLED feedback** while a track plays.

This is **V0.1** (still home-lab scope; no cloud API or LLM in this folder).

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
| `GET` | `/` | HTML landing page: Music Agent Player, future skills text, buttons per manifest track. |
| `GET` | `/api/tracks` | JSON array of `{ "id", "title" }` from manifest. |
| `GET` | `/health` | Returns OK (and optional manifest stats). Query `?oled=1` refreshes the OLED with host + idle line (`idle N trk` or `!no manifest`). |
| `POST` | `/play` | Body: `{ "track_id": "track_1" }` — lookup manifest, resolve file, run **mpv** (with IPC socket when meter enabled), update **OLED** (`mm:ss / total` + VU-style meter while playing). |
| `POST` | `/stop` | Stop playback; OLED **STOPPED**. |

**Dependencies:** `mpv`, Python web stack, OLED library (e.g. `luma.oled` as in the main Pi repo).

**Success:** `curl` `POST /play` → sound + OLED update.

**Suggested default port:** **`8766`** (lets you run **V0.0** on `8765` side-by-side). Override with uvicorn `--port`.

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

Use **`curl`**, [`mac/pi_player.sh`](mac/pi_player.sh), or a **Mac browser**:

- Open **`http://<pi-ip>:8765/`** — the server redirects to **`/docs`** (FastAPI **Swagger**). Use **Try it out** on `GET /health`, `POST /play` (body `{"track_id": "track_1"}`), and `POST /stop`.
- Or open **`http://<pi-ip>:8765/health`** for raw JSON only (no play/stop buttons).

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
v0_1/
  README.md
  OPERATORS.md
  manifest.example.json
  requirements-pi.txt
  requirements-dev.txt
  scripts/smoke_v0_1.sh
  mac/pi_player.sh
  pi/
    player_server.py
    mpv_ipc.py
    oled_meter.py
    oled_status.py
    tests/
```

Parent repo reference for OLED/audio patterns: `../../` (e.g. `oled_linein_level_meter.py`, venv at repo root).

---

## Run on the Pi

**Python:** Either use the repo root [`.venv`](../../.venv) (already includes `luma.oled` and can add FastAPI with `pip install -r music-agent-orchestration/v0_1/requirements-pi.txt`) or create `music-agent-orchestration/v0_1/.venv` and install from [`requirements-pi.txt`](requirements-pi.txt).

**System:** `mpv` installed; I2C enabled for the OLED.

**Paths:** Put audio under `~/music-agent/media/` (or set `MEDIA_ROOT`). Copy [`manifest.example.json`](manifest.example.json) to `music-agent-orchestration/v0_1/manifest.json` and adjust `id` / `title` / `filename` (or use `path_on_pi` — that wins over `filename` when both are set).

**Environment (optional):**

| Variable | Meaning |
|----------|---------|
| `MANIFEST_PATH` | Default: `v0_1/manifest.json` next to this README’s folder |
| `MEDIA_ROOT` | Default: `~/music-agent/media` |
| `MPV_BIN` | Default: `mpv` |
| `MPV_OPTS` | Extra args (e.g. ALSA device). Discover names on the Pi: `aplay -L` / `aplay -l` |
| `DISABLE_OLED` | Set to `1` for headless / tests (no hardware) |
| `DISABLE_PLAYBACK_METER` | Set to `1` to skip mpv IPC + OLED meter thread (tests default this). |
| `PLAYBACK_METER_MODE` | `ffmpeg` (default) estimates RMS dB for VU meter; `none` keeps clock + pulse fallback without dB probing. |
| `OLED_REFRESH_SECONDS` | OLED draw interval (default `0.08`). Lower = faster refresh, higher CPU. Range clamp: `0.03..0.5`. |
| `DB_PROBE_INTERVAL_SECONDS` | dB probe interval when `PLAYBACK_METER_MODE=ffmpeg` (default `0.35`). Lower = snappier meter, higher CPU. Range clamp: `0.1..2.0`. |
| `I2C_PORT` | Default `1` |
| `I2C_ADDR` | Default `0x3C` |

**Start the server** (from repo root, default port **8766**):

```bash
cd /home/uzan/Raspberri_Pi_Audio
source .venv/bin/activate
cd music-agent-orchestration/v0_1
python -m uvicorn pi.player_server:app --host 0.0.0.0 --port 8766
```

Then on your **Mac** (same LAN), open **`http://<pi-ip>:8766/`** — Music Agent landing page; **Swagger** remains at **`/docs`**.

---

## Quick terminal control

Find the Pi IP on the Pi itself:

```bash
hostname -I
```

Example output:

```text
192.168.68.65
```

Play `track_1` (replace IP as needed):

```bash
curl -sS -X POST "http://192.168.68.65:8766/play" \
  -H "Content-Type: application/json" \
  -d '{"track_id":"track_1"}'
```

Stop playback:

```bash
curl -sS -X POST "http://192.168.68.65:8766/stop"
```

---

## Testing

### Layer 1 — Automated (pytest)

From `music-agent-orchestration/v0_1` (repo clone):

```bash
cd music-agent-orchestration/v0_1
/path/to/.venv/bin/pip install -r requirements-dev.txt
/path/to/.venv/bin/python -m pytest pi/tests -q
```

Uses `DISABLE_OLED` via `conftest.py`; mocks `mpv` where needed.

### Layer 2 — Pi-local smoke

With the server listening on `127.0.0.1:8766`, use `curl` or:

```bash
bash scripts/smoke_v0_1.sh
```

You still confirm **audio** and **OLED** manually (P2–P5 in the implementation plan).

### Layer 3 — End-to-end checklist (Mac → Pi)

Prereq: Pi running uvicorn on `0.0.0.0:8766`, Mac on same LAN, TCP 8766 allowed.

```bash
export PI=http://<pi-ip>:8766

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
export PI_BASE_URL=http://<pi-ip>:8766
bash mac/pi_player.sh health
bash mac/pi_player.sh play '<valid_id>'
bash mac/pi_player.sh stop
```
