🎵 Raspberry Pi 5 – Real-Time BPM Estimator

Stable real-time BPM detection using a Raspberry Pi 5 and Steinberg UR22.

Designed for:

Live mix input

Headless operation (SSH)

Low CPU footprint

Simple CLI execution

⚙️ System

Hardware

Raspberry Pi 5

Steinberg UR22 USB Audio Interface

OS

Raspberry Pi OS Bookworm 64-bit Lite

Audio

ALSA capture

44.1 kHz

Stereo → mono mix

Python

aubio 0.4.9

numpy

sounddevice

🧠 Architecture

The estimator works as follows:

Capture stereo input via sounddevice

Convert to mono

Detect beats using aubio.tempo()

Store IOIs (Inter-Onset Intervals) in a sliding window

Compute:

BPM = 60 / mean(IOI)


Output BPM every 2 seconds

No reset calls.
No unnecessary DSP layers.
No over-engineering.

Stable > clever.

🚀 Install
sudo apt install python3-pip
pip3 install numpy sounddevice aubio


Or if using requirements:

pip3 install -r requirements.txt

▶ Run
python3 bpm.py


Output example:

BPM: 125.4
BPM: 125.5


Updates every 2 seconds.

🔌 Shutdown & Resume

Shutdown safely:

sudo shutdown now


Resume:

ssh pi@<your_pi_ip>
cd ~
python3 bpm.py

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

✅ Current Status

✔ Stable beat detection
✔ Reliable BPM lock
✔ Low CPU usage
✔ Clean restart behavior
✔ Production-ready baseline

🔮 Future Directions

OLED / HDMI display output

OSC / MQTT network broadcast

ML pitch tracking process

systemd auto-start

Web dashboard

Version: 1.0
Status: Stable baseline
