from __future__ import annotations

import time

import numpy as np
from openwakeword.model import Model

from core.event_bus import publish
from voice.microphone_manager import (
    microphone_manager,
)


class OpenWakeWordEngine:
    """
    Wake-word detector using Baby's shared microphone stream.

    The microphone stays open when Baby moves from wake-word
    detection into active speech recognition.
    """

    def __init__(
        self,
        wake_word: str = "hey_jarvis",
        threshold: float = 0.75,
        cooldown_seconds: float = 2.0,
    ) -> None:
        self.wake_word = wake_word
        self.threshold = threshold
        self.cooldown_seconds = (
            cooldown_seconds
        )

        self.last_trigger_time = 0.0

        self.model = Model(
            wakeword_models=[],
            inference_framework="onnx",
        )

        microphone_manager.start()

    def wait_for_wake_word(
        self,
    ) -> str:
        publish(
            "wake_listening",
            {},
        )

        print(
            "Waiting for wake word..."
        )

        microphone_manager.clear()

        while True:
            frame = (
                microphone_manager.get_frame(
                    timeout=1.0
                )
            )

            if frame is None:
                continue

            # openWakeWord expects PCM int16.
            pcm = np.clip(
                frame.samples * 32767.0,
                -32768,
                32767,
            ).astype(
                np.int16
            )

            prediction = (
                self.model.predict(
                    pcm
                )
            )

            current_time = time.monotonic()

            for key, score in (
                prediction.items()
            ):
                if (
                    key == self.wake_word
                    and score
                    >= self.threshold
                    and current_time
                    - self.last_trigger_time
                    >= self.cooldown_seconds
                ):
                    self.last_trigger_time = (
                        current_time
                    )

                    print(
                        f"Wake word detected: "
                        f"{key} "
                        f"({score:.2f})"
                    )

                    publish(
                        "wake_detected",
                        {
                            "wake_word": key,
                            "score": float(
                                score
                            ),
                        },
                    )

                    # Remove remaining wake-word audio,
                    # so ASR doesn't transcribe "Jarvis".
                    microphone_manager.clear()

                    return key

    def close(self) -> None:
        microphone_manager.stop()