"""OLED boot/status rotator for v0_2 (SSID, IP, CPU/MEM, and ready screen)."""

from __future__ import annotations

import os
import signal
import subprocess
import time

from . import oled_status

_HANDOFF_FILE = "/tmp/music-agent-v01-oled.handoff"


def _truncate(text: str, n: int) -> str:
    t = (text or "").strip()
    if len(t) <= n:
        return t
    if n <= 3:
        return t[:n]
    return t[: n - 3] + "..."


def _run_text(cmd: list[str]) -> str:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5, check=False)
    except Exception:
        return ""
    return (p.stdout or "").strip()


def _ssid() -> str:
    ssid = _run_text(["iwgetid", "-r"])
    if ssid:
        return ssid
    # Fallback to nmcli active line format: yes:<ssid>
    out = _run_text(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"])
    for line in out.splitlines():
        if line.startswith("yes:"):
            return line.split(":", 1)[1].strip()
    return "no wifi"


def _ipv4() -> str:
    out = _run_text(["hostname", "-I"])
    for token in out.split():
        if "." in token and ":" not in token:
            return token
    return "no ip"


def _cpu_percent(interval_s: float = 0.25) -> int:
    def sample() -> tuple[int, int]:
        with open("/proc/stat", encoding="utf-8") as f:
            parts = f.readline().split()
        nums = [int(x) for x in parts[1:8]]
        total = sum(nums)
        idle = nums[3] + nums[4]
        return total, idle

    t1, i1 = sample()
    time.sleep(interval_s)
    t2, i2 = sample()
    dt = max(1, t2 - t1)
    di = max(0, i2 - i1)
    used = 100.0 * (1.0 - (di / dt))
    return max(0, min(100, int(round(used))))


def _mem_percent() -> int:
    mt = 0
    ma = 0
    with open("/proc/meminfo", encoding="utf-8") as f:
        for line in f:
            if line.startswith("MemTotal:"):
                mt = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                ma = int(line.split()[1])
    if mt <= 0:
        return 0
    used = 100.0 * (1.0 - (ma / mt))
    return max(0, min(100, int(round(used))))


def _handoff_active() -> bool:
    if not os.path.exists(_HANDOFF_FILE):
        return False
    try:
        with open(_HANDOFF_FILE, encoding="utf-8") as f:
            raw = (f.read() or "").strip()
    except OSError:
        return True
    if not raw:
        return True
    try:
        pid = int(raw)
    except ValueError:
        return True
    if os.path.exists(f"/proc/{pid}"):
        return True
    # Stale marker from a dead process.
    try:
        os.unlink(_HANDOFF_FILE)
    except OSError:
        pass
    return False


_running = True


def _handle_signal(_sig, _frame):
    global _running
    _running = False


def main() -> int:
    global _running
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    host = _truncate(_run_text(["hostname"]) or "pi", 21)
    interval = float(os.environ.get("OLED_BOOT_STATUS_INTERVAL_SECONDS", "2.0") or "2.0")
    interval = max(0.5, min(10.0, interval))

    while _running:
        if _handoff_active():
            break

        ssid = _truncate(_ssid(), 16)
        ip = _truncate(_ipv4(), 16)
        cpu = _cpu_percent()
        mem = _mem_percent()

        pages = [
            (host, f"wifi {ssid}"),
            ("IP ADDRESS", ip),
            ("CPU/MEM", f"{cpu}% / {mem}%"),
            ("AI AGENT READY", ip),
        ]
        for t, s in pages:
            if not _running:
                break
            oled_status.show_status(t, s)
            time.sleep(interval)

    oled_status.show_status(host, "handoff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
