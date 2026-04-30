# v0.2 cloud setup (S3 + Lambda presign)

This folder is the minimal cloud side for `v0_2`:

- `handler.py` provides two endpoints via Lambda Function URL:
  - `GET /tracks` returns `id` + `title`
  - `POST /play` with `{"track_id":"..."}` returns a short-lived S3 presigned URL
- `catalog.example.json` maps `track_id` to `s3_key`
- `iam-policy.example.json` is least-privilege `s3:GetObject` for `tracks/*`

## 1) Prepare S3

1. Create or choose a private bucket (Block Public Access ON).
2. Upload three demo tracks under a stable prefix:
   - `tracks/que_maravilla.mp3`
   - `tracks/javi_mula_come_on.mp3`
   - `tracks/luke_million_italo_journey.mp3`
3. Copy `catalog.example.json` to `catalog.json` and keep `s3_key` values aligned with uploaded objects.

## 2) Create Lambda role

Use the policy from `iam-policy.example.json`, replacing `YOUR_BUCKET_NAME`.
Attach this inline policy to the Lambda execution role.

## 3) Deploy Lambda

1. Runtime: Python 3.12
2. Upload a zip that contains at least:
   - `handler.py`
   - `catalog.json`
3. Set handler to `handler.handler`
4. Environment variables:
   - `S3_BUCKET=<your bucket name>`
   - `API_SHARED_SECRET=<random shared key>`
   - `PRESIGN_TTL_SECONDS=300`
   - optional: `CATALOG_PATH=/var/task/catalog.json`

## 4) Function URL

1. Enable Function URL (HTTPS).
2. For this lab version, you can use Auth type `NONE` and enforce access with `X-Api-Key` checked in `handler.py`.
3. Note the URL, for example:
   - `https://abcde12345.lambda-url.us-east-1.on.aws`

## 5) Validate Lambda before Pi

Use your shared key:

```bash
export LAMBDA_URL="https://abcde12345.lambda-url.us-east-1.on.aws"
export CLOUD_KEY="replace-me"
curl -sS -H "X-Api-Key: ${CLOUD_KEY}" "${LAMBDA_URL}/tracks"
curl -sS -X POST -H "X-Api-Key: ${CLOUD_KEY}" -H "Content-Type: application/json" "${LAMBDA_URL}/play" -d '{"track_id":"que_maravilla"}'
```

If `/play` returns `presigned_url`, copy it and test:

```bash
mpv --no-video "<presigned_url>"
```

## 6) Wire into Pi `v0_2`

Create `v0_2/.env.local` from the template and keep real values there:

```bash
cd /home/uzan/Raspberri_Pi_Audio/music-agent-orchestration/v0_2
cp .env.example .env.local
```

Set these in `.env.local`:

- `LAMBDA_FUNCTION_URL=<function-url>`
- `CLOUD_API_KEY=<same value as API_SHARED_SECRET>`
- `PLAYBACK_METER_MODE=none` (recommended for cloud playback in v0.2)

Then start:

```bash
cd /home/uzan/Raspberri_Pi_Audio
source .venv/bin/activate
cd music-agent-orchestration/v0_2
bash scripts/run_v0_2.sh
```

This pattern generalizes to other clouds:
- S3 presign (AWS)
- Signed URL (GCS)
- SAS token (Azure Blob)

The control-plane separation remains the same: API authorizes + mints short-lived access, player reads bytes directly from object storage.
