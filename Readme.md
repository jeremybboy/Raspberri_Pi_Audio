# 🎵 Raspberry Pi 5 – Real-Time BPM Estimator

Stable real-time BPM detection using a Raspberry Pi 5 and Steinberg UR22.

---

## ⚙️ System

**Hardware**
- Raspberry Pi 5  
- Steinberg UR22 USB Audio Interface  

**OS**
- Raspberry Pi OS Bookworm 64-bit Lite  

**Audio**
- ALSA capture  
- 44.1 kHz  
- Stereo → mono mix  

**Python**
- aubio 0.4.9  
- numpy  
- sounddevice  

---

## 🐍 Setup (Recommended: Virtual Environment)

```bash
mkdir realtime-bpm
cd realtime-bpm
python3 -m venv .venv
source .venv/bin/activate
pip install numpy sounddevice aubio
```

---

## ▶ Run

```bash
python3 bpm.py
```

---

## 🔁 After Reboot / New SSH Session

```bash
cd ~/realtime-bpm
source .venv/bin/activate
python3 bpm.py
```

---

## 🧠 Architecture

1. Capture stereo input via `sounddevice`
2. Convert to mono
3. Detect beats using `aubio.tempo()`
4. Store IOIs (Inter-Onset Intervals)
5. Compute:

```
BPM = 60 / mean(IOI)
```

6. Print BPM every 2 seconds

---

## 📊 Processing Flow

```json
{
  "audio_input": "Steinberg UR22",
  "capture": "ALSA 44.1kHz",
  "stream": "sounddevice InputStream",
  "beat_detection": "aubio.tempo()",
  "buffer": "IOI sliding window",
  "bpm_calc": "60 / mean(IOI)",
  "output": "CLI (2s interval)"
}
```

---

## ✅ Status

✔ Stable  
✔ Low CPU  
✔ Production-ready baseline  

---

**Version:** 1.0
