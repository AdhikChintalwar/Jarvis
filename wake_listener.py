import pyaudio
import numpy as np
from openwakeword.model import Model

model = Model(
    wakeword_models=[],
    inference_framework="onnx"
)

CHUNK = 1280
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

audio = pyaudio.PyAudio()

stream = audio.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=CHUNK
)

print("Waiting for wake word...")

while True:
    audio_data = stream.read(CHUNK, exception_on_overflow=False)

    frame = np.frombuffer(audio_data, dtype=np.int16)

    prediction = model.predict(frame)

    for key, score in prediction.items():
        if score > 0.5:
            print(f"Wake word detected: {key}")