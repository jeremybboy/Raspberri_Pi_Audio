"""Lambda handler for v0.2 track list + presigned playback URLs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import boto3

_S3 = boto3.client("s3")


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _catalog_path() -> Path:
    raw = os.environ.get("CATALOG_PATH", "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().with_name("catalog.json")


def _load_catalog() -> dict[str, dict[str, str]]:
    text = _catalog_path().read_text(encoding="utf-8")
    doc = json.loads(text)
    tracks = doc.get("tracks", [])
    out: dict[str, dict[str, str]] = {}
    for item in tracks:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id", "")).strip()
        s3_key = str(item.get("s3_key", "")).strip()
        if not tid or not s3_key:
            continue
        title = str(item.get("title") or tid).strip() or tid
        out[tid] = {"title": title, "s3_key": s3_key}
    return out


def _json(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _check_api_key(event: dict[str, Any]) -> bool:
    expected = _env("API_SHARED_SECRET")
    headers = event.get("headers") or {}
    if not isinstance(headers, dict):
        return False
    got = headers.get("x-api-key") or headers.get("X-Api-Key") or ""
    return str(got).strip() == expected


def _list_tracks(catalog: dict[str, dict[str, str]]) -> dict[str, Any]:
    rows = [{"id": tid, "title": item["title"]} for tid, item in sorted(catalog.items())]
    return _json(200, rows)


def _play(event: dict[str, Any], catalog: dict[str, dict[str, str]]) -> dict[str, Any]:
    raw = event.get("body") or "{}"
    body = json.loads(raw)
    track_id = str(body.get("track_id", "")).strip()
    if not track_id:
        return _json(400, {"detail": "track_id is required"})
    if track_id not in catalog:
        return _json(404, {"detail": f"Unknown track_id: {track_id!r}"})

    item = catalog[track_id]
    bucket = _env("S3_BUCKET")
    ttl_raw = os.environ.get("PRESIGN_TTL_SECONDS", "300").strip()
    try:
        ttl = max(30, min(3600, int(ttl_raw)))
    except ValueError:
        ttl = 300

    presigned_url = _S3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": item["s3_key"]},
        ExpiresIn=ttl,
    )
    return _json(
        200,
        {
            "track_id": track_id,
            "title": item["title"],
            "expires_in": ttl,
            "presigned_url": presigned_url,
        },
    )


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    if not _check_api_key(event):
        return _json(401, {"detail": "Unauthorized"})

    catalog = _load_catalog()
    path = str(event.get("rawPath") or "/")
    method = str(event.get("requestContext", {}).get("http", {}).get("method") or "").upper()

    if method == "GET" and path.endswith("/tracks"):
        return _list_tracks(catalog)
    if method == "POST" and path.endswith("/play"):
        return _play(event, catalog)
    return _json(404, {"detail": "Not found"})
