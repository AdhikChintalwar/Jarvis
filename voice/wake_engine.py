import time
import numpy as np
from openwakeword.model import Model

from voice.microphone import open_microphone_stream, CHUNK


class OpenWakeWordEngine:
    def __init__(
        self,
        wake_word: str = "hey_jarvis",
        threshold: float = 0.75,
        cooldown_seconds: int = 2
    ):
        self.wake_word = wake_word
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self.last_trigger_time = 0

        self.model = Model(
            wakeword_models=[],
            inference_framework="onnx"
        )

        self.audio, self.stream = open_microphone_stream()

    def wait_for_wake_word(self):
        print("Waiting for wake word...")

        while True:
            audio_data = self.stream.read(
                CHUNK,
                exception_on_overflow=False
            )

            frame = np.frombuffer(audio_data, dtype=np.int16)
            prediction = self.model.predict(frame)

            for key, score in prediction.items():
                current_time = time.time()

                if (
                    key == self.wake_word
                    and score > self.threshold
                    and current_time - self.last_trigger_time > self.cooldown_seconds
                ):
                    self.last_trigger_time = current_time
                    print(f"Wake word detected: {key}")
                    return key

    def close(self):
        try:
            self.stream.stop_stream()
            self.stream.close()
            self.audio.terminate()
        except Exception:
            pass
