"""Minimal mpv JSON IPC client over Unix socket."""

from __future__ import annotations

import json
import logging
import socket
from typing import Any

log = logging.getLogger(__name__)


def ipc_call(sock_path: str, command: list[Any], timeout: float = 0.5) -> dict[str, Any]:
    """Send one JSON-RPC command; return parsed response dict."""
    payload = json.dumps({"command": command}) + "\n"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout)
        sock.connect(sock_path)
        sock.sendall(payload.encode("utf-8"))
        buf = b""
        while True:
            chunk = sock.recv(8192)
            if not chunk:
                break
            buf += chunk
            if b"\n" in buf:
                line = buf.split(b"\n", 1)[0]
                return json.loads(line.decode("utf-8"))
    except OSError as e:
        log.debug("mpv ipc error: %s", e)
        return {"error": str(e)}
    finally:
        try:
            sock.close()
        except OSError:
            pass
    return {"error": "no_response"}


def get_percent_pos(sock_path: str) -> float | None:
    r = ipc_call(sock_path, ["get_property", "percent-pos"])
    err = r.get("error")
    if err not in (None, "success"):
        return None
    data = r.get("data")
    if data is None:
        return None
    try:
        return float(data)
    except (TypeError, ValueError):
        return None


def _get_float_property(sock_path: str, prop: str) -> float | None:
    r = ipc_call(sock_path, ["get_property", prop])
    err = r.get("error")
    if err not in (None, "success"):
        return None
    data = r.get("data")
    if data is None:
        return None
    try:
        return float(data)
    except (TypeError, ValueError):
        return None


def get_time_pos(sock_path: str) -> float | None:
    return _get_float_property(sock_path, "time-pos")


def get_duration(sock_path: str) -> float | None:
    return _get_float_property(sock_path, "duration")
