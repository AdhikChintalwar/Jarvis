import time
import queue
import numpy as np
import sounddevice as sd
import sherpa_onnx


SAMPLE_RATE = 16000
DEVICE_ID = 4

SILENCE_THRESHOLD = 0.02
SILENCE_SECONDS = 1.0
MAX_SECONDS = 12

MODEL_DIR = "models/sensevoice/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"


def create_recognizer():
    return sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=f"{MODEL_DIR}/model.int8.onnx",
        tokens=f"{MODEL_DIR}/tokens.txt",
        num_threads=4,
        use_itn=True,
        debug=False,
    )


def record_until_silence() -> np.ndarray:
    audio_queue = queue.Queue()
    chunks = []

    speech_started = False
    last_speech_time = time.time()
    start_time = time.time()

    def callback(indata, frames, callback_time, status):
        if status:
            print(status)
        audio_queue.put(indata.copy())

    print("Listening with SenseVoice... speak now")

    with sd.InputStream(
        device=DEVICE_ID,
        channels=1,
        samplerate=SAMPLE_RATE,
        dtype="float32",
        callback=callback,
    ):
        while True:
            chunk = audio_queue.get()
            volume = float(np.max(np.abs(chunk)))

            if volume > SILENCE_THRESHOLD:
                speech_started = True
                last_speech_time = time.time()

            if speech_started:
                chunks.append(chunk)

            if speech_started and time.time() - last_speech_time > SILENCE_SECONDS:
                break

            if time.time() - start_time > MAX_SECONDS:
                break

    if not chunks:
        return np.array([], dtype=np.float32)

    return np.concatenate(chunks, axis=0).reshape(-1)


def listen_sensevoice() -> str:
    audio = record_until_silence()

    if audio.size == 0:
        print("No speech detected.")
        return ""

    recognizer = create_recognizer()
    stream = recognizer.create_stream()

    stream.accept_waveform(SAMPLE_RATE, audio)
    recognizer.decode_stream(stream)

    text = stream.result.text.strip()

    print("Final:", text)
    return text