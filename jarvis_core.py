import time
import os
import wave
import pyaudio
import numpy as np
import threading
import requests
import re
from wakeonlan import send_magic_packet
from piper import PiperVoice, SynthesisConfig
from anthropic import Anthropic
from openwakeword.model import Model
from pywhispercpp.model import Model as WhisperModel

WHISPER= WhisperModel("/home/dademadeluis/whisper.cpp/models/ggml-tiny.en.bin")

VOICE = PiperVoice.load(
	"/home/dademadeluis/.local/share/piper-tts/jarvis-medium.onnx"
)
SYN= SynthesisConfig(length_scale=1.3)

OWW = Model(wakeword_model_paths=[
	"/home/dademadeluis/jarvis_env/lib/python3.13/site-packages/openwakeword/resources/models/hey_jarvis_v0.1.onnx"
])

JUNK = ("dramatic music", "bye")

MEMORY_FILE = "/home/dademadeluis/jarvis/memory.txt"
HISTORY = []
MAX_TURNS = 10

LAT, LON = 25.9420, -80.2456  # Miami Gardens, Florida

WEATHER_CODES = {
	0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
	45: "foggy", 48: "foggy", 51: "drizzling", 53: "drizzling", 55: "drizzling",
	61: "raining lightly", 63: "raining", 65: "raining heavily",
	80: "showering", 81: "showering", 82: "pouring",
	95: "thunderstorming", 96: "thunderstorming", 99: "thunderstorming",
}

ONES = {
	"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
	"six": 6, "seven": 7, "eight": 8, "nine": 9,
}
TEENS = {
	"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
	"fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
TENS = {
	"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
	"sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

STOPWATCH_START = None

JOURNAL_FILE = "/home/dademadeluis/jarvis/journal.txt"

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

def speak(message, stream=None):
	with wave.open('/tmp/speak.wav', 'wb') as wav_file:
		VOICE.synthesize_wav(message, wav_file, syn_config=SYN)
	if stream:
		stream.stop_stream()
	os.system('aplay -q /tmp/speak.wav')
	if stream:
		stream.start_stream()

def record_until_silence(stream, filename, max_seconds=10, silence_limit=1.2, threshold=700):
	frames, silent, started = [], 0, False
	chunks_per_sec = RATE / CHUNK

	for _ in range (int(chunks_per_sec * 0.1)):
		stream.read(CHUNK, exception_on_overflow=False)

	for _ in range(int(chunks_per_sec * max_seconds)):
		data = stream.read(CHUNK, exception_on_overflow=False)
		frames.append(data)
		samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
		rms= np.sqrt(np.mean(samples ** 2))
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

def load_memory():
	try:
		with open(MEMORY_FILE) as f:
			return f.read().strip()
	except FileNotFoundError:
		return ""

MEMORY = load_memory()

BASE_PROMPT = (
	"You are Jarvis, a voice assistant. Your replies are read aloud "
	"by a text-to-speech engine, so write plain spoken prose only. "
	"Never use asterisks, markdown, bullet points, headers, or any "
	"formatting characters. Keep replies to one or two short sentences "
	"unless asked for detail. User is in miami gardens florida so tailor "
	"responses around that. Add a space before the beginning of the first "
	"word of the first sentence of the response. Address the user as Sir."
)

def build_prompt():
	if MEMORY:
		return BASE_PROMPT + " Here is what you know about the user: " + MEMORY
	return BASE_PROMPT

def get_claude_response(user_message, client):
	HISTORY.append({"role": "user", "content": user_message})
	try:
		response = client.messages.create(
			model="claude-haiku-4-5-20251001",
			max_tokens=100,
			system=build_prompt(),
			messages=HISTORY[-MAX_TURNS:]
		)
		reply = response.content[0].text
		HISTORY.append({"role": "assistant", "content": reply})
		return reply
	except Exception as e:
		print("API error:", e)
		HISTORY.pop()
		return " I'm having trouble connecting to the server, Sir."

def remember(fact):
	global MEMORY
	with open(MEMORY_FILE, "a") as f:
		f.write(fact.strip() + "\n")
	MEMORY = load_memory()

def get_weather():
	try:
		r = requests.get(
			"https://api.open-meteo.com/v1/forecast",
			params={
				"latitude": LAT, "longitude": LON,
				"current": "temperature_2m,weather_code",
				"temperature_unit": "fahrenheit",
			},
			timeout=8,
		)
		cur = r.json()["current"]
		temp = round(cur["temperature_2m"])
		desc = WEATHER_CODES.get(cur["weather_code"], "unclear")
		return f" It is {temp} degrees and {desc}, Sir"
	except Exception as e:
		print("Weather error:", e)
		return " I couldn't reach the weather service, Sir"

def start_timer(seconds, label, stream):
	def fire():
		speak(f" Your {label} timer is up, Sir")
	t = threading.Timer(seconds, fire)
	t.daemon = True
	t.start()

def words_to_numbers(text):
	for tens_word, tens_val in TENS.items():
		for ones_word, ones_val in ONES.items():
			text = text.replace(f"{tens_word} {ones_word}", str(tens_val + ones_val))
			text = text.replace(f"{tens_word}-{ones_word}", str(tens_val + ones_val))
	for word, val in list(TENS.items()) + list(TEENS.items()) + list(ONES.items()):
		text = text.replace(word, str(val))
	return text

def parse_duration(text):
	text = words_to_numbers(text)
	m = re.search(r"(\d+)\s*(second|minute|hour)", text)
	if not m:
		return None, None
	n = int(m.group(1))
	unit = m.group(2)
	mult = {"second": 1, "minute": 60, "hour": 3600}[unit]
	return n * mult, f"{n} {unit}" + ("s" if n != 1 else "")

def stopwatch_start():
	global STOPWATCH_START
	STOPWATCH_START = time.time()
	return " Stopwatch started, Sir"

def stopwatch_read():
	if STOPWATCH_START is None:
		return " No stopwatch is running, Sir"
	elapsed = int(time.time() - STOPWATCH_START)
	mins, secs = divmod(elapsed, 60)
	hours, mins = divmod(mins, 60)
	if hours:
		return f" {hours} hours, {mins} minutes and {secs} seconds, Sir"
	if mins:
		return f" {mins} minutes and {secs} seconds, Sir"
	return f" {secs} seconds, Sir"

def stopwatch_stop():
	global STOPWATCH_START
	if STOPWATCH_START is None:
		return " No stopwatch is running, Sir"
	reading = stopwatch_read()
	STOPWATCH_START = None
	return " Stopped at" + reading

def log_entry(entry):
	stamp = time.strftime("%Y-%m-%d %H:%M")
	with open(JOURNAL_FILE, "a") as f:
		f.write(f"[{stamp}] {entry.strip()}\n")

def read_journal(n=3):
	try:
		with open(JOURNAL_FILE) as f:
			lines = [l.strip() for l in f if l.strip()]
	except FileNotFoundError:
		return " Your journal is empty, Sir"
	if not lines:
		return " Your journal is empty, Sir"
	return " " + ". ".join(lines[-n:])

def wake_computer (mac_address, stream=None):
	"""Wake PC via Wake-on-Lan"""
	if not mac_address:
		speak("No computer address is configured, Sir", stream)
		return
	speak("waking your computer", stream)
	send_magic_packet(mac_address)
	time.sleep(5)
	speak("Computer is booting", stream)

def handle_command(text, client, stream):
	lowered = text.lower()

	if "wake" in lowered and ("computer" in lowered or "pc" in lowered):
		wake_computer(PC_MAC, stream)
		return

	if "what time" in lowered or "what's the time" in lowered:
		speak(time.strftime(" It is %I:%M %p, Sir").replace(" 0", " ", 1), stream)
		return

	if "what's the date" in lowered or "what is the date" in lowered or "what day is it" in lowered:
		speak(time.strftime(" It is %A, %B %d, Sir"), stream)
		return

	if "go to sleep" in lowered or "shut down" in lowered or "goodnight" in lowered:
		speak(" Going offline, Sir", stream)
		raise KeyboardInterrupt

	if lowered.startswith("remember that") or lowered.startswith("remember i"):
		fact = text.split(" ", 1)[1]
		remember(fact)
		speak(" Noted, Sir", stream)
		return

	if "weather" in lowered or "temperature" in lowered or "how hot" in lowered:
		speak(get_weather(), stream)
		return

	if "start the stopwatch" in lowered or "start a stopwatch" in lowered:
		speak(stopwatch_start(), stream)
		return

	if "stop the stopwatch" in lowered or "stop stopwatch" in lowered:
		speak(stopwatch_stop(), stream)
		return

	if "stopwatch" in lowered:
		speak(stopwatch_read(), stream)
		return
	
	if "cancel the timer" in lowered or "stop the timer" in lowered:
		speak(" I can't cancel timers yet, Sir", stream)
		return
	
	if "timer" in lowered or "remind me in" in lowered:
		secs, label = parse_duration(lowered)
		if secs:
			start_timer(secs, label, stream)
			speak(f" Timer set for {label}, Sir", stream)
		else:
			speak(" I didn't catch the duration, Sir", stream)
		return

	if lowered.startswith("log ") or " log that" in lowered or lowered.startswith("journal "):
		log_entry(text.split(" ", 1)[1])
		speak(" Logged, Sir", stream)
		return

	if "read my journal" in lowered or "recent entries" in lowered:
		speak(read_journal(), stream)
		return

	speak(get_claude_response(text, client), stream)

PC_MAC = os.environ.get("JARVIS_PC_MAC", "")
API_KEY = os.environ.get("ANTHROPIC_API_KEY")

if not API_KEY:
	raise SystemExit("ANTHROPIC_API_KEY is not set. Run: export ANTHROPIC_API_KEY=sk-ant-...")

if __name__ == "__main__":
	client = Anthropic(api_key=API_KEY)

	p = pyaudio.PyAudio()
	stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)

	speak(" Goodmorning Sir", stream)
	OWW.reset()
	print(" Listening for wake word...")

	try:
		while True:
			data = stream.read(CHUNK, exception_on_overflow=False)
			audio = np.frombuffer(data, dtype=np.int16)

			prediction = OWW.predict(audio)
			score = max(prediction.values())
			if score > 0.7:
				print(f"Wake word detected ({score:.2f})")
				speak(" Yes sir?", stream)
				drain(stream, 0.4)
				OWW.reset()

				if record_until_silence(stream, "/tmp/command.wav"):
					text = transcribe_audio("/tmp/command.wav")
					print("HEARD:", repr(text))
					if text and not is_junk(text):
						handle_command(text, client, stream)
				
				drain(stream, 0.4)
				OWW.reset()
				for _ in range(20):
					OWW.predict(np.zeros(CHUNK, dtype=np.int16))
				print("Listening for wake word...")
	except KeyboardInterrupt:
		stream.stop_stream()
		stream.close()
		p.terminate()
