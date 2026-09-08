import pyaudio
import wave

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 2
p = pyaudio.PyAudio()

print("Available devices:")
for i in range(p.get_device_count()):
	info = p.get_device_info_by_index(i)
	print(f"{i}: {info['name']}")

print("\nTrying device 3...")
try:
	stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
	print("Recording...")
	frames = [stream.read(CHUNK) for _ in range(int(RATE / CHUNK * RECORD_SECONDS))]
	stream.stop_stream()
	stream.close()

	wf = wave.open('/tmp/test.wav', 'wb')
	wf.setnchannels(CHANNELS)
	wf.setsampwidth(p.get_sample_size(FORMAT))
	wf.setframerate(RATE)
	wf.writeframes(b''.join(frames))
	wf.close()
	print("Success! File saved.")
except Exception as e:
	print(f"Error: {e}")

p.terminate()
