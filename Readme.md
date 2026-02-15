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
▶ Run
python3 bpm.py
🔁 After Reboot / New SSH Session
cd ~/realtime-bpm
source .venv/bin/activate
python3 bpm.py
🧠 Architecture
Capture stereo input via sounddevice

Convert to mono

Detect beats using aubio.tempo()

Store IOIs (Inter-Onset Intervals)

Compute:

BPM = 60 / mean(IOI)
Print BPM every 2 seconds

📊 Processing Flow
{
  "audio_input": "Steinberg UR22",
  "capture": "ALSA 44.1kHz",
  "stream": "sounddevice InputStream",
  "beat_detection": "aubio.tempo()",
  "buffer": "IOI sliding window",
  "bpm_calc": "60 / mean(IOI)",
  "output": "CLI (2s interval)"
}
✅ Status
✔ Stable
✔ Low CPU
✔ Production-ready baseline

Version: 1.0


---

That will render cleanly with sections, spacing, and code blocks.

If it still looks bad, it means you accidentally removed a backtick or blank line.
