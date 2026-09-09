Jarvis

A voice assistant running on a Raspberry Pi 4. Wake word detection and speech recognition run locally on the device; only the language model call leaves the Pi.

Pipeline
Wake word — openWakeWord listens continuously for "hey Jarvis" on a 1280-sample rolling buffer at 16 kHz
Recording — captures until RMS amplitude drops below threshold for 1.2s, so it stops when you stop talking instead of on a fixed timer
Transcription — whisper.cpp (ggml-tiny.en) runs on-device, no network call
Response — Claude Haiku, prompted for spoken prose since the output goes to a speech engine rather than a screen
Speech — Piper TTS with a custom voice model, played through ALSA

All three models stay resident in memory. Loading them per request added roughly five seconds of latency each time, most of it spent reading the same weights off the SD card.

Audio feedback loop

The assistant kept triggering on its own replies. The microphone buffer fills continuously, so audio recorded during playback was read back in a burst the moment the reply finished — replaying the wake word that started the exchange.

Fixed by stopping the input stream during playback so nothing accumulates, then flushing openWakeWord's rolling feature window afterward. reset() clears the score history but not the feature window, so stale audio could still trigger a match on the next read.

Features
Local command routing — timers, stopwatch, weather, date and time resolve on-device before any API call, so common requests are instant and cost nothing
Memory — a plain-text file of user facts injected into the system prompt, writable by voice ("remember that...")
Conversation history — the last five exchanges are kept in context, so follow-up questions resolve against what was already said
Voice journal — timestamped entries appended by voice
Wake-on-LAN — boots my desktop by voice via magic packet
Junk filtering — discards whisper's bracketed non-speech artifacts ([dramatic music], etc.) before they reach the model
Hardware

Raspberry Pi 4, USB microphone, speaker over 3.5mm. A GPIO status LED for listening/processing/idle states is in progress.

Setup
python3 -m venv jarvis_env
source jarvis_env/bin/activate
pip install pyaudio numpy requests wakeonlan piper-tts anthropic openwakeword pywhispercpp

Models are downloaded separately:

Piper voice — a .onnx and matching .onnx.json from piper-voices
whisper.cpp — build from source, then bash ./models/download-ggml-model.sh tiny.en
openWakeWord — the hey_jarvis model ships with the pip package

Model paths in jarvis_core.py are absolute and will need adjusting for your system.


export ANTHROPIC_API_KEY=sk-ant-...
export JARVIS_PC_MAC=00-00-00-00-00-00
python3 jarvis_core.py
Deployment

Runs as a systemd service that starts on boot and restarts on failure. Copy jarvis.service.example to /etc/systemd/system/jarvis.service, add your API key, then:


sudo systemctl daemon-reload
sudo systemctl enable --now jarvis
journalctl -u jarvis -f

Stop the service before editing the source — Restart=always will otherwise loop on a syntax error.