#!/usr/bin/env python3
"""Create ~/music-agent/media demo WAVs matching manifest.json (track_1 / track_2)."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


def write_tone(path: Path, seconds: float = 0.8, freq: float = 440.0, sr: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(seconds * sr)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        for i in range(n):
            v = int(32767 * 0.15 * math.sin(2 * math.pi * freq * i / sr))
            w.writeframes(struct.pack("<h", v))


def main() -> None:
    root = Path.home() / "music-agent" / "media"
    write_tone(root / "v0_0_demo.wav", freq=523.25)
    write_tone(root / "v0_0_demo2.wav", freq=392.0)
    print(f"Wrote {root / 'v0_0_demo.wav'} and {root / 'v0_0_demo2.wav'}")


if __name__ == "__main__":
    main()
