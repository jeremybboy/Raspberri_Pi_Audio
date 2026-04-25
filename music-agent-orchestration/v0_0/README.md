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

## Suggested layout (you implement)

```text
v0_0/
  README.md                 # this spec
  manifest.example.json     # contract example
  pi/                       # Pi HTTP server + OLED + mpv (your code)
  mac/                      # optional: tiny CLI or curl wrapper
```

Parent repo reference for OLED/audio patterns: `../../` (e.g. `oled_linein_level_meter.py`, venv at repo root).
