### Raspberry Pi 5 Real-Time BPM Pedal

This project is a standalone Raspberry Pi 5 device that captures live audio from a USB interface and displays a stable real-time BPM on an SH1106 OLED using an autocorrelation-based estimator.
Audio is captured at 44.1 kHz via ALSA, mixed to mono, converted to an energy envelope, buffered (~8s), processed with FFT autocorrelation, peak-detected, folded into 90–180 BPM, smoothed with hysteresis, and rendered to the OLED.
Hardware: Raspberry Pi 5, Behringer UCA202 (USB Audio CODEC), SH1106 I2C OLED (0x3C); Software: Raspberry Pi OS Bookworm Lite 64-bit, Python venv, numpy, sounddevice, luma.oled, pillow.
The engine prioritizes stability over instant lock, achieves accurate tempo tracking with low CPU usage on Pi 5, and is designed for live pedal-style operation.
Planned improvements include faster initial lock via dual-window estimation, silence hold behavior, beat phase indication, and systemd appliance-mode autostart.





