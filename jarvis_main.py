import os
import time
import pyaudio
import numpy as np
from openwakeword.model import Model

from core.offline_listener import listen_offline
from core.executor import execute_command


WAKE_THRESHOLD = 0.75
COOLDOWN_SECONDS = 4
IS_BUSY = False


def speak(text: str):
    os.system(f'say "{text}"')


def is_valid_command(text: str) -> bool:
    if not text:
        return False

    text = text.strip().lower()

    if len(text) < 3:
        return False

    bad_phrases = [
        "thank you",
        "thanks",
        "bye",
        "you",
        ".",
        ","
    ]

    return text not in bad_phrases


def should_stop(command_text: str) -> bool:
    command_text_lower = command_text.lower()

    return (
        "stop baby" in command_text_lower
        or "exit baby" in command_text_lower
        or "stop jarvis" in command_text_lower
        or "exit jarvis" in command_text_lower
    )


def start_baby():
    global IS_BUSY

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

    speak("Baby is ready")
    print("Waiting for wake word...")

    last_trigger_time = 0

    while True:
        audio_data = stream.read(CHUNK, exception_on_overflow=False)
        frame = np.frombuffer(audio_data, dtype=np.int16)

        prediction = model.predict(frame)

        for key, score in prediction.items():
            current_time = time.time()

            if (
                key == "hey_jarvis"
                and score > WAKE_THRESHOLD
                and current_time - last_trigger_time > COOLDOWN_SECONDS
                and not IS_BUSY
            ):
                last_trigger_time = current_time
                IS_BUSY = True

                print(f"Wake word detected: {key}")
                speak("Yes")

                time.sleep(0.5)

                command_text = listen_offline()
                print("Heard command:", command_text)

                if should_stop(command_text):
                    speak("Baby stopped")
                    print("Baby stopped.")
                    return

                if not is_valid_command(command_text):
                    print("Ignored empty/noisy command.")
                    IS_BUSY = False
                    print("Cooling down...")
                    time.sleep(COOLDOWN_SECONDS)
                    print("Waiting for wake word again...")
                    continue

                try:
                    execute_command(command_text, speak)

                except Exception as e:
                    print("Error while executing command:", e)
                    speak("Something went wrong")

                IS_BUSY = False

                print("Cooling down...")
                time.sleep(COOLDOWN_SECONDS)

                print("Waiting for wake word again...")


if __name__ == "__main__":
    start_baby()