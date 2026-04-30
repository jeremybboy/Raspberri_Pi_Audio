"""Layer 1 API tests (no mpv hardware)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from pi.player_server import CloudPlay, _fetch_tracks_from_cloud, app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_root_landing_html(client: TestClient) -> None:
    with patch(
        "pi.player_server._fetch_tracks_from_cloud",
        return_value=[{"id": "a", "title": "Alpha"}],
    ):
        r = client.get("/")
    assert r.status_code == 200
    assert "Music Agent Player" in r.text
    assert "/docs" in r.text


def test_api_tracks(client: TestClient) -> None:
    with patch(
        "pi.player_server._fetch_tracks_from_cloud",
        return_value=[{"id": "a", "title": "Alpha"}, {"id": "b", "title": "Beta"}],
    ):
        r = client.get("/api/tracks")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["id"] == "a"
    assert data[1]["title"] == "Beta"


def test_fetch_tracks_legacy_shape_track_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAMBDA_FUNCTION_URL", "https://lambda.example.test")
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "tracks": [
            {"track_id": "one_more_time", "title": "One More Time"},
            {"track_id": "mezigue", "title": "Mezigue - Track 1"},
        ]
    }
    with patch("pi.player_server.httpx.get", return_value=fake_resp):
        rows = _fetch_tracks_from_cloud(force=True)
    assert rows[0]["id"] == "one_more_time"
    assert rows[1]["title"] == "Mezigue - Track 1"


def test_health_oled_query_ok(client: TestClient) -> None:
    with patch(
        "pi.player_server._fetch_tracks_from_cloud",
        return_value=[],
    ):
        r = client.get("/health", params={"oled": True})
    assert r.status_code == 200
    assert r.json()["track_count"] == 0


def test_health_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAMBDA_FUNCTION_URL", "https://lambda.example.test")
    with patch(
        "pi.player_server._fetch_tracks_from_cloud",
        return_value=[{"id": "a", "title": "A"}],
    ):
        r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["track_count"] == 1
    assert data["lambda_configured"] is True


def test_play_cloud_404(client: TestClient) -> None:
    from fastapi import HTTPException

    with patch(
        "pi.player_server._request_cloud_play",
        side_effect=HTTPException(status_code=404, detail="Unknown track_id: 'nope'"),
    ):
        r = client.post("/play", json={"track_id": "nope"})
    assert r.status_code == 404


def test_play_success_mocks_mpv(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setenv("LAMBDA_FUNCTION_URL", "https://lambda.example.test")
    fake = MagicMock()
    fake.poll.return_value = None
    cloud_play = CloudPlay(
        track_id="a",
        title="Hello",
        presigned_url="https://signed.example/path.mp3",
        expires_in=300,
        lambda_host="lambda.example.test",
    )
    with patch("pi.player_server.subprocess.Popen", return_value=fake) as popen, patch(
        "pi.player_server._request_cloud_play", return_value=cloud_play
    ):
        r = client.post("/play", json={"track_id": "a"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    popen.assert_called_once()
    args, _kwargs = popen.call_args
    assert "mpv" in args[0][0] or args[0][0] == "mpv"
    assert cloud_play.presigned_url in args[0]


def test_stop_ok(client: TestClient) -> None:
    r = client.post("/stop")
    assert r.status_code == 200
    assert r.json()["ok"] is True
