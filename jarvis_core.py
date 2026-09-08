import time
import os
import wave
import pyaudio
import numpy as np
from wakeonlan import send_magic_packet
from piper import PiperVoice
from anthropic import Anthropic
from openwakeword.model import Model
from pywhispercpp.model import Model as WhisperModel

WHISPER= WhisperModel("/home/dademadeluis/whisper.cpp/models/ggml-tiny.en.bin")

VOICE = PiperVoice.load(
	"/home/dademadeluis/.local/share/piper-tts/jarvis-medium.onnx"
)
OWW = Model(wakeword_model_paths=[
	"/home/dademadeluis/jarvis_env/lib/python3.13/site-packages/openwakeword/resources/models/hey_jarvis_v0.1.onnx"
])

JUNK = ("dramatic music", "bye")

CHUNK = 1280
RATE = 16000

def is_junk(text):
	t = text.lower().strip(" .!?,")
	if text.strip().startswith(("[","(")):
		return True
	return len(t) < 3 or t in JUNK

def drain(stream, seconds=1.0):
	for _ in range(int((RATE / CHUNK) * seconds)):
		stream.read(CHUNK, exception_on_overflow=False)

def speak(message):
	with wave.open('/tmp/speak.wav', 'wb') as wav_file:
		VOICE.synthesize_wav(message, wav_file)
	os.system('aplay -q /tmp/speak.wav')

def record_until_silence(stream, filename, max_seconds=10, silence_limit=1.2, threshold=700):
	frames, silent, started = [], 0, False
	chunks_per_sec = RATE / CHUNK

	for _ in range (int(chunks_per_sec * 1.5)):
		stream.read(CHUNK, exception_on_overflow=False)

	for _ in range(int(chunks_per_sec * max_seconds)):
		data = stream.read(CHUNK, exception_on_overflow=False)
		frames.append(data)
		samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
		rms= np.sqrt(np.mean(samples ** 2))
		print(f"rms {rms:.0f}", end=" ", flush=True)
		if rms > threshold:
			started, silent = True, 0
		elif started:
			silent += 1
			if silent > chunks_per_sec * silence_limit:
				break

	wf = wave.open(filename, 'wb')
	wf.setnchannels(1)
	wf.setsampwidth(2)
	wf.setframerate(RATE)
	wf.writeframes(b''.join(frames))
	wf.close()
	return started

def transcribe_audio(audio_file):
	segments = WHISPER.transcribe(audio_file)
	return ' '.join([s.text for s in segments]).strip()

def get_claude_response(user_message, client):
	response = client.messages.create(
		model="claude-haiku-4-5-20251001",
		max_tokens=100,
		system=(
			"You are Jarvis, a voice assistant. Your replies are read aloud "
			"by a text-to-speech engine, so write plain spoken prose only. "
			"Never use asterisks, markdown, bullet points, headers, or any "
			"formatting characters. Keep replies to one or two short sentences "
			"unless asked for detail. User is in  miami gardens florida so tailor "
			"responses around that.Add a space before the beginning of the first "
			"word of the first sentence of the response. Address the user as Sir."
		),
		messages=[
			{"role": "user", "content": user_message}
		]
	)
	return response.content[0].text

def wake_computer (mac_address):
	"""Wake PC via Wake-on-Lan"""
	speak("waking your computer")
	send_magic_packet(mac_address)
	time.sleep(5)
	speak("Computer is booting")

<<<<<<< HEAD
PC_MAC = "XX-XX-XX-XX-XX-XX"  # your PC's MAC address for Wake-on-LAN
=======
PC_MAC = os.environ.get("JARVIS_PC_MAC", "")
>>>>>>> e09d5b5 (Move PC MAC address to environment variable)
API_KEY = os.environ.get("ANTHROPIC_API_KEY")

if not API_KEY:
	raise SystemExit("ANTHROPIC_API_KEY is not set. Run: export ANTHROPIC_API_KEY=sk-ant-...")

if __name__ == "__main__":
	client = Anthropic(api_key=API_KEY)

	p = pyaudio.PyAudio()
	stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)

	speak(" Goodmorning Sir")
	print(" Listening for wake word...")

	try:
		while True:
			data = stream.read(CHUNK, exception_on_overflow=False)
			audio = np.frombuffer(data, dtype=np.int16)

			prediction = OWW.predict(audio)
			if max(prediction.values()) > 0.5:
				print("Wake word detected")
				speak(" Yes sir?")
				OWW.reset()

				if record_until_silence(stream, "/tmp/command.wav"):
					text = transcribe_audio("/tmp/command.wav")
					print("HEARD:", repr(text))
					if text:
						speak(get_claude_response(text, client))
				OWW.reset()
				print("Listening for wake word...")
	except KeyboardInterrupt:
		stream.stop_stream()
		stream.close()
		p.terminate()
