"""Layer 1 API tests (no mpv hardware)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from pi.player_server import app, resolve_audio_path


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_health_oled_query_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    m = tmp_path / "manifest.json"
    m.write_text(json.dumps({"tracks": []}), encoding="utf-8")
    monkeypatch.setenv("MANIFEST_PATH", str(m))
    r = client.get("/health", params={"oled": True})
    assert r.status_code == 200
    assert r.json()["track_count"] == 0


def test_health_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    m = tmp_path / "manifest.json"
    m.write_text(
        json.dumps({"tracks": [{"id": "a", "title": "A", "filename": "x.mp3"}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MANIFEST_PATH", str(m))
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["manifest_exists"] is True
    assert data["track_count"] == 1
    assert data["manifest_path"]


def test_play_unknown_track(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    m = tmp_path / "manifest.json"
    m.write_text(json.dumps({"tracks": [{"id": "a", "title": "A", "filename": "x.mp3"}]}), encoding="utf-8")
    monkeypatch.setenv("MANIFEST_PATH", str(m))
    r = client.post("/play", json={"track_id": "nope"})
    assert r.status_code == 404


def test_play_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    media = tmp_path / "media"
    media.mkdir()
    m = tmp_path / "manifest.json"
    m.write_text(
        json.dumps({"tracks": [{"id": "a", "title": "A", "filename": "missing.mp3"}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MANIFEST_PATH", str(m))
    monkeypatch.setenv("MEDIA_ROOT", str(media))
    r = client.post("/play", json={"track_id": "a"})
    assert r.status_code == 400
    assert "missing" in r.json()["detail"].lower() or "File missing" in r.json()["detail"]


def test_play_success_mocks_mpv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    media = tmp_path / "media"
    media.mkdir()
    f = media / "t.wav"
    f.write_bytes(b"RIFF")
    m = tmp_path / "manifest.json"
    m.write_text(
        json.dumps({"tracks": [{"id": "a", "title": "Hello", "filename": "t.wav"}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MANIFEST_PATH", str(m))
    monkeypatch.setenv("MEDIA_ROOT", str(media))
    fake = MagicMock()
    fake.poll.return_value = None
    with patch("pi.player_server.subprocess.Popen", return_value=fake) as popen:
        r = client.post("/play", json={"track_id": "a"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    popen.assert_called_once()
    args, kwargs = popen.call_args
    assert "mpv" in args[0][0] or args[0][0] == "mpv"
    assert str(f.resolve()) in args[0]


def test_stop_ok(client: TestClient) -> None:
    r = client.post("/stop")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_resolve_path_on_pi_wins(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    wrong = media / "wrong.mp3"
    wrong.write_bytes(b"x")
    right = tmp_path / "right.mp3"
    right.write_bytes(b"y")
    entry = {
        "id": "x",
        "filename": "wrong.mp3",
        "path_on_pi": str(right),
    }
    p = resolve_audio_path(entry, media)
    assert p == right.resolve()


def test_resolve_filename_under_media_root(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    f = media / "a.mp3"
    f.write_bytes(b"z")
    entry = {"id": "a", "title": "T", "filename": "a.mp3"}
    p = resolve_audio_path(entry, media)
    assert p == f.resolve()


def test_resolve_neither_raises() -> None:
    with pytest.raises(ValueError):
        resolve_audio_path({"id": "a"}, Path("/tmp"))
