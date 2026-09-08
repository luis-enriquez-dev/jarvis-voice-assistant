# Jarvis

A voice assistant running on a Raspberry Pi 4. Wake word detection and speech
recognition run locally on the device; only the language model call leaves the Pi.

## Pipeline

1. **Wake word** — openWakeWord listens continuously for "hey Jarvis" on a
   1280-sample rolling buffer at 16 kHz
2. **Recording** — captures until RMS amplitude drops below threshold for 1.2s,
   so it stops when you stop talking instead of on a fixed timer
3. **Transcription** — whisper.cpp (ggml-tiny.en) runs on-device, no network call
4. **Response** — Claude Haiku, prompted for spoken prose since the output goes
   to a speech engine rather than a screen
5. **Speech** — Piper TTS with a custom voice model, played through ALSA

## Other features

- **Wake-on-LAN** — boots my desktop by voice via magic packet
- **Junk filtering** — discards whisper's bracketed non-speech artifacts
  (`[dramatic music]`, etc.) before they reach the model

## Hardware

Raspberry Pi 4, USB microphone, speaker over 3.5mm. A GPIO status LED for
listening/processing/idle states is in progress.

## Setup

```bash
python3 -m venv jarvis_env
source jarvis_env/bin/activate
pip install pyaudio numpy wakeonlan piper-tts anthropic openwakeword pywhispercpp

export ANTHROPIC_API_KEY=sk-ant-...
export JARVIS_PC_MAC=00-00-00-00-00-00
python3 jarvis_core.py
```

Model paths in `jarvis_core.py` are absolute and will need adjusting for your system.
