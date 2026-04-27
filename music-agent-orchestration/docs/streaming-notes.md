# Adaptive streaming (HLS and DASH) — context for this project

This note captures **why** HLS (HTTP Live Streaming) and DASH (Dynamic Adaptive Streaming over HTTP) exist, **what they cost** to implement, and **why we are not building that layer in the current phase** — so future work can build on a shared mental model instead of re-opening the same design questions.

---

## Why HLS and DASH exist

HLS and DASH are **HTTP-based delivery systems** aimed at **real-world networks**: bandwidth fluctuates, and clients want to **start playback quickly** without downloading one enormous file first. They do that by publishing a **manifest** that points to a **ladder of renditions** (multiple bitrates or resolutions, sometimes separate audio) and splitting media into **short segments**. A player reads the manifest, fetches segments in order, and can **switch renditions** based on buffer and throughput — that is **adaptive bitrate (ABR)** in the familiar “streaming” sense.

---

## What that costs in implementation

Adaptive streaming is **not a single codec or file format**; it is a **packaging and distribution shape**. A serious implementation must:

- **Organize storage** as manifest plus **many segment objects** (and often multiple renditions per title).
- **Cut and package** media on sensible segment boundaries, often with a **transcoding pipeline** (`ffmpeg`, packagers, etc.) to produce the ladder.
- Implement or embed **ABR logic** (buffer estimation, switching rules, oscillation control, stall recovery).
- Handle **live** vs **on-demand** semantics (sliding playlists, MPD updates for DASH live profiles).
- Deal with **containers** (often fMP4 or MPEG-TS), **sync across segment boundaries**, optional **encryption/DRM**, **CDN caching**, and **player integration** (custom headers, HTTPS everywhere).

Teams usually rely on **mature players and CDNs** for much of this because the **edge-case surface** is large compared to “play one file from disk or from a single HTTPS URL.”

---

## What this repository is doing instead (and why)

In this phase we are building **home-lab infrastructure** around a **small catalog on the order of ~10 tracks**: a **Raspberry Pi** player over the LAN, **`mpv`**, a **manifest contract**, and incremental steps toward **Mac-side orchestration** and **cloud-backed fetch** when we deliberately add them. The priority is **reliable control + playback + a stable HTTP API seam** to the Pi, not operating a full **HLS/DASH packaging and ABR pipeline**.

We are **explicitly not implementing HLS/DASH here yet** because:

- The **engineering and operational cost** (segmentation, ladders, packaging jobs, storage layout, player edge cases) is **disproportionate** to a **tiny static library** at this stage.
- **Simpler patterns** — **download or cache** the object to the Pi, or use **HTTP Range** on a **single** stored object where appropriate — already cover “play from the cloud” for small libraries with far less moving surface.
- **`v0_0`** remains the **regression anchor** for the Pi player; advanced delivery belongs in a **later milestone** with its own success criteria, not mixed into the first control-plane iterations.

---

## Why we still document this

We keep HLS/DASH in **shared context** so we do not confuse **“streaming as in Spotify-scale adaptive delivery”** with **“fetch bytes from cloud storage and play on a Pi.”** When the catalog, latency goals, or UX truly require **adaptive segmented delivery**, the [roadmap](roadmap.md) can add an **explicit milestone** for packaging and ABR — without rewriting the core **play/stop/health** story.

---

## See also

- [Roadmap — phased next steps](roadmap.md)
- [Architecture diagram](architecture.md)
- [V0.0 operator guide (Pi + Mac control)](../v0_0/OPERATORS.md)
