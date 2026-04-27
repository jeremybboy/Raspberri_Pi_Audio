# Music agent orchestration — implementation roadmap

Ordered phases for moving from the **V0.0** wedge to **Mac orchestration**, **optional LLM (Ollama)**, and **cloud-backed bytes** — while keeping **`v0_0`** testable and relevant. Adjust dates and owners as you go; the **intent** is stable ordering and exit criteria.

---

## Phase 0 — V0.0 remains the regression anchor (ongoing)

**Goal:** The Pi **HTTP player** under [`v0_0/`](../v0_0/) stays **correct, documented, and pytest-green** even as other folders grow.

**Includes:** `GET /health`, `POST /play`, `POST /stop`, manifest + `mpv` + OLED, [`OPERATORS.md`](../v0_0/OPERATORS.md).

**Exit criteria:** `cd v0_0 && python -m pytest pi/tests -q` passes on `main` (or CI when added); operator doc reflects how to start **Uvicorn** and control from Mac.

**Rule of thumb:** Change **`v0_0`** only when fixing or extending the **Pi player contract**; do not fold unrelated features into that tree.

---

## Phase 1 — Mac control plane without LLM (thin client)

**Goal:** The **Mac** (or any LAN client) reliably drives the **same** Pi API using **`mac/pi_player.sh`**, **`curl`**, or Swagger — no new server on the Mac unless you choose to.

**Exit criteria:** Documented env (`PI_BASE_URL` / `PI_PLAYER_BASE_URL`), repeatable **play → stop** from Mac to Pi for every `track_id` in the Pi manifest.

---

## Phase 2 — Ollama chooses `track_id` (still same Pi API)

**Goal:** [`mac/orchestrator_cli.py`](../mac/orchestrator_cli.py) (or a successor) reads a **Mac-side manifest**, asks **Ollama** for a **`track_id`**, then **POSTs `/play`** to the Pi — **no Mac web UI required** unless you add one later.

**Exit criteria:** One command or documented flow: natural-language prompt → valid **`track_id`** → sound on Pi.

**Note:** This phase does **not** require Dropbox **API** on the Pi; a **Dropbox-synced folder on the Mac** plus manifest is enough for the library source.

---

## Phase 3 — Cloud fetch (Dropbox API, S3 presigned URLs, or hybrid)

**Goal:** Bytes for a requested track arrive on the Pi (or at **`mpv`**) via **explicit cloud pull or signed URL**, with **tokens or signing** handled in a deliberate, documented place (Pi vs Mac).

**Exit criteria:** `play` works for at least one track whose bytes are **not** pre-copied manually to `~/music-agent/media/`, with clear failure modes (auth, 404, disk).

**See:** [Streaming and adaptive delivery context](streaming-notes.md) — **HLS/DASH** remain **out of scope** here until a separate milestone justifies packaging complexity.

---

## Phase 4 (optional) — Catalog and polish

**Goal:** Larger library, indexing, nicer operator UX, or **HLS/DASH** only if product goals require **true adaptive segmented delivery** at scale.

**Exit criteria:** Defined per initiative; link from this file when opened.

---

## Relationship to “Roadmap (after v0)” in the parent README

The bullets under **Roadmap (after v0)** in [`../README.md`](../README.md) (Dropbox API on Pi, skills plane, catalog index) are **longer-horizon** themes. This file is the **stepping-stone path** that gets you there without skipping the **stable Pi API** and **Mac orchestration** foundation.

---

## Related docs

- [Streaming notes — HLS/DASH vs this phase](streaming-notes.md)
- [Architecture](architecture.md)
- [V0.0 operator guide](../v0_0/OPERATORS.md)
