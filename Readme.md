# 🎵 Raspberry Pi 5 – Real-Time BPM Estimator

Stable real-time BPM detection on Raspberry Pi 5 using USB audio input and SH1106 OLED display.

---

## ⚙️ System Overview

### Hardware
- Raspberry Pi 5  
- USB Audio Interface (tested with Behringer UCA202)  
- SH1106 I²C OLED (address `0x3C`)

### OS
- Raspberry Pi OS Bookworm 64-bit Lite  

### Audio
- ALSA capture  
- 44.1 kHz  
- Stereo → mono mix  

### Python
- numpy  
- sounddevice  
- luma.oled  
- pillow  

---

## 🐍 Setup

### 1️⃣ Create Project Folder

```bash
mkdir realtime-bpm
cd realtime-bpm
2️⃣ Create Virtual Environment
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
3️⃣ Install Dependencies
pip install numpy sounddevice luma.oled pillow
🔌 Enable I²C (OLED Required)
sudo raspi-config
# Interface Options → I2C → Enable
sudo reboot

Verify OLED is detected:

i2cdetect -y 1

You should see 3c.

▶ Run the Program

Autocorrelation version (recommended):

python3 bpm_oled_autocorr_fast.py
🔁 After Reboot / New SSH Session
cd ~/realtime-bpm
source .venv/bin/activate
python3 bpm_oled_autocorr_fast.py
🧠 Architecture
Processing Pipeline

Capture stereo audio via sounddevice

Convert to mono

Rectify + low-pass filter → energy envelope

Maintain rolling buffer (~8 seconds)

Compute FFT-based autocorrelation

Detect dominant periodicity (lag peak)

Convert lag → BPM

Apply half/double-time folding

Apply hysteresis smoothing

Display BPM on OLED

📊 Processing Flow
{
  "audio_input": "USB Audio Interface",
  "capture": "ALSA 44.1kHz",
  "stream": "sounddevice InputStream",
  "preprocess": "rectify + envelope smoothing",
  "analysis": "FFT-based autocorrelation",
  "tempo_model": "dominant lag peak + folding",
  "stability": "hysteresis smoothing",
  "output": "OLED display"
}
🎯 Why Autocorrelation Instead of IOI Averaging

Autocorrelation provides:

Multi-bar periodicity detection

Resistance to onset timing bias

Reduced ±2–3 BPM drift

More stable long-term tempo lock

This approach behaves closer to professional DJ equipment tempo modeling.

✅ Status

✔ Stable lock

✔ No consistent BPM offset

✔ Low CPU usage (Pi 5)

✔ Real-time OLED display

✔ Robust against silence / resume

🔜 Future Improvements

Auto-start via systemd

Silence hold mode

Downbeat detection

Beat phase visualization

Tap-tempo input

Version: 2.0 – Autocorrelation Engine
Platform: Raspberry Pi 5

::contentReference[oaicite:0]{index=0}
