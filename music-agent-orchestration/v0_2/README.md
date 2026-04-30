# Music agent orchestration — V0.2

Self-contained workspace under `music-agent-orchestration/v0_2/`.  
This version keeps the v0.1 Pi UX but moves playback bytes to cloud:

- **Pi API remains the controller** (`/`, `/api/tracks`, `/play`, `/stop`).
- **Lambda is the authorization + catalog endpoint**.
- **S3 stores private audio objects**.
- **mpv still runs on the Pi** and plays over HTTPS using presigned URLs.

## What changed from v0.1

- v0.1: local manifest + local files on Pi.
- v0.2: cloud-authoritative catalog (`GET /tracks`) and presign API (`POST /play`) behind Lambda.

See:
- [OPERATORS.md](OPERATORS.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [cloud/README.md](cloud/README.md)

## Quick start (Pi)

```bash
cd /home/uzan/Raspberri_Pi_Audio
source .venv/bin/activate
cd music-agent-orchestration/v0_2
pip install -r requirements-pi.txt
cp .env.example .env.local
# edit .env.local with real values (this file is gitignored)
bash scripts/run_v0_2.sh
```

Then on Mac open:
- `http://<pi-ip>:8767/`

## Notes

- `PLAYBACK_METER_MODE=none` is the recommended default for cloud mode in v0.2.
- `ffmpeg` dB probing on presigned URLs may increase S3 traffic and fail on short expiry windows.
- Keep v0.1 available as local-file regression baseline.
- Runtime secrets should stay in `.env.local` (gitignored) or exported env vars; keep docs and committed files anonymized.
