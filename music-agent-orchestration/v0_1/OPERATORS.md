# V0.1 operator guide — run, visualize, test, add tracks

Single-page reference for **GitHub** and day-to-day use: how to **start the Pi player**, **control it from a Mac** (browser or shell), **run tests**, and **add songs**.

**Default port:** **`8766`** (run **[V0.0](../v0_0/)** on **`8765`** side-by-side if needed).

---

## Flow (what talks to what)

```mermaid
flowchart LR
  MacBrowser[Mac_browser]
  Landing[GET_slash_HTML]
  Swagger[Pi_Swagger_docs]
  API[FastAPI_8766]
  MPV[mpv_IPC_ALSA]
  OLED[OLED_meter]
  MacBrowser -->|"http://pi-host:8766"| Landing
  MacBrowser --> Swagger
  Landing --> API
  Swagger --> API
  API --> MPV
  API --> OLED
```

Audio is heard **on the Pi** (USB interface → speakers/headphones), not on the Mac speakers.

---

## Start the player (always on the Raspberry Pi)

Run **`uvicorn`** from this folder so imports resolve (`pi.*`):

```bash
cd /path/to/Raspberri_Pi_Audio/music-agent-orchestration/v0_1
/path/to/.venv/bin/python -m uvicorn pi.player_server:app --host 0.0.0.0 --port 8766
```

Use the repo [`.venv`](../../.venv) path on your Pi, or another venv with `requirements-pi.txt` installed.

---

## Control from the Mac (visual first)

| Goal | What to do on the Mac |
|------|------------------------|
| **Landing + track buttons** | Open **`http://<pi-hostname-or-ip>:8766/`** — Music Agent Player page with **Play** buttons per manifest track and **Stop**. |
| **Swagger API** | **`http://<pi-host>:8766/docs`** |
| **JSON track list** | **`http://<pi-host>:8766/api/tracks`** |
| **Status JSON only** | **`http://<pi-host>:8766/health`** |
| **Refresh OLED idle line** | **`http://<pi-host>:8766/health?oled=1`** |

Use your Pi’s LAN hostname (e.g. **`jeremybboy.local`**) or IP instead of `<pi-host>`.

---

## Same actions from the terminal (Mac or Pi)

Set the base URL once:

```bash
export PI_BASE_URL=http://jeremybboy.local:8766
# or: export PI_BASE_URL=http://192.168.x.x:8766
```

From anywhere in a clone, using the helper script:

```bash
bash music-agent-orchestration/v0_1/mac/pi_player.sh health
bash music-agent-orchestration/v0_1/mac/pi_player.sh play 'que_maravilla'
bash music-agent-orchestration/v0_1/mac/pi_player.sh stop
```

Equivalent **`curl`**:

```bash
curl -sS "$PI_BASE_URL/health"
curl -sS "$PI_BASE_URL/api/tracks"
curl -sS -X POST "$PI_BASE_URL/play" -H 'Content-Type: application/json' -d '{"track_id":"que_maravilla"}'
curl -sS -X POST "$PI_BASE_URL/stop"
```

---

## OLED playback meter

While a track plays, **mpv** runs with **`--input-ipc-server`** (unless **`DISABLE_PLAYBACK_METER=1`**) and a background thread polls **`percent-pos`** to draw a **progress bar** on the SH1106.

Tests and CI set **`DISABLE_PLAYBACK_METER=1`** via [`pi/tests/conftest.py`](pi/tests/conftest.py).

---

## Add a new song

| Step | Action |
|------|--------|
| 1 | Copy the audio file onto the Pi under **`~/music-agent/media/`** (default `MEDIA_ROOT`). Example from Mac: `scp "/path/to/Song.mp3" uzan@<pi-host>:~/music-agent/media/` |
| 2 | Prefer **no spaces** in the filename on disk (e.g. `Song.mp3`) to avoid shell/JSON mistakes. |
| 3 | Edit **`music-agent-orchestration/v0_1/manifest.json`** on the Pi and add a track object: **`id`** (this is the **`track_id`** you send in **`/play`**), **`title`** (OLED line), **`filename`** (must match the file name under `MEDIA_ROOT`). |
| 4 | **Optional:** use **`path_on_pi`** with an absolute path on the Pi; it **overrides** **`filename`** when both are set. See [`pi/player_server.py`](pi/player_server.py) function `resolve_audio_path`. |
| 5 | Reload **`/`** in the browser or call **`/api/tracks`** to see the new row; **Play** from the landing page or **`POST /play`**. |

`manifest.json` is usually **local only** (ignored by git under `music-agent-orchestration/.gitignore`). Keep a backup or maintain [`manifest.example.json`](manifest.example.json) in the repo as a template.

**Demo WAVs on a fresh Pi:** from `v0_1/`, run `python scripts/setup_demo_media.py` then copy `manifest.example.json` to `manifest.json` if needed.

---

## Run tests (layers)

| Layer | What it checks | Command (from **`music-agent-orchestration/v0_1/`**) |
|-------|----------------|------------------------------------------------------|
| **1 — Automated** | HTTP API, manifest paths, mocked **`mpv`** | `pip install -r requirements-dev.txt` then `python -m pytest pi/tests -q` |
| **2 — Smoke** | You confirm **sound + OLED** while server runs on `127.0.0.1:8766` | `bash scripts/smoke_v0_1.sh` (interactive; prompts for `track_id`) |
| **3 — LAN** | Mac (or browser) → Pi over the network | Landing **`/`**, **`/docs`**, **`PI_BASE_URL`** + `pi_player.sh` / `curl` as above |

---

## Troubleshooting (short)

| Symptom | Likely cause |
|---------|----------------|
| Browser cannot open Pi URL | Pi off, wrong host, not same LAN, firewall, or **`uvicorn`** not bound to **`0.0.0.0:8766`**. |
| **`/docs`** fails | Server not running or wrong port. |
| **404** on **`/play`** | **`track_id`** does not match any **`id`** in **`manifest.json`**. |
| **400** missing file | **`filename`** wrong or file not under **`MEDIA_ROOT`**. |
| **200** but no sound | Wrong ALSA device for **`mpv`**; set **`MPV_OPTS`** (see main [`README.md`](README.md) env table). |
| OLED shows **`!no manifest`** | **`manifest.json`** missing at default path, or **`uvicorn`** was started from the **wrong directory** — always **`cd`** into **`v0_1`** before starting the server. |

---

## More context

- Full spec and steps: [`README.md`](README.md) in this folder.  
- Stable baseline (V0.0): [`../v0_0/README.md`](../v0_0/README.md).  
- Parent “full v0” vision (Dropbox + Ollama): [`../README.md`](../README.md).
