from __future__ import annotations

import queue
import threading
from dataclasses import dataclass

import numpy as np
import sounddevice as sd


SAMPLE_RATE = 16000
BLOCKSIZE = 480  # 30 ms @ 16 kHz


@dataclass
class AudioFrame:
    samples: np.ndarray
    rms: float


class MicrophoneManager:
    """
    One shared persistent microphone stream for Baby.

    Wake-word detection and ASR use the SAME underlying microphone.
    """

    def __init__(
        self,
        *,
        sample_rate: int = SAMPLE_RATE,
        blocksize: int = BLOCKSIZE,
    ) -> None:
        self.sample_rate = sample_rate
        self.blocksize = blocksize

        self.device_id = self._find_input_device()

        if self.device_id is None:
            raise RuntimeError(
                "No microphone input device was found."
            )

        self._queue: queue.Queue[AudioFrame] = queue.Queue(
            maxsize=500
        )

        self._stream: sd.InputStream | None = None
        self._lock = threading.RLock()
        self._running = False

    def start(self) -> None:
        with self._lock:
            if self._running:
                return

            device_info = sd.query_devices(
                self.device_id
            )

            print(
                f"Microphone: "
                f"{device_info['name']} "
                f"(device {self.device_id})"
            )

            self._stream = sd.InputStream(
                device=self.device_id,
                channels=1,
                samplerate=self.sample_rate,
                dtype="float32",
                blocksize=self.blocksize,
                latency="low",
                callback=self._callback,
            )

            self._stream.start()
            self._running = True

            print("Shared microphone stream started.")

    def stop(self) -> None:
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                except Exception:
                    pass

                try:
                    self._stream.close()
                except Exception:
                    pass

            self._stream = None
            self._running = False

            self.clear()

            print("Shared microphone stream stopped.")

    def get_frame(
        self,
        *,
        timeout: float = 1.0,
    ) -> AudioFrame | None:
        if not self._running:
            self.start()

        try:
            return self._queue.get(
                timeout=timeout
            )
        except queue.Empty:
            return None

    def clear(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _callback(
        self,
        indata,
        frames,
        callback_time,
        status,
    ) -> None:
        if status:
            print("Microphone status:", status)

        samples = np.asarray(
            indata[:, 0],
            dtype=np.float32,
        ).copy()

        rms = float(
            np.sqrt(
                np.mean(
                    np.square(samples)
                )
                + 1e-12
            )
        )

        frame = AudioFrame(
            samples=samples,
            rms=rms,
        )

        try:
            self._queue.put_nowait(frame)

        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass

            try:
                self._queue.put_nowait(frame)
            except queue.Full:
                pass

    @staticmethod
    def _find_input_device() -> int | None:
        devices = sd.query_devices()

        preferred_names = [
            "MacBook Pro Microphone",
            "MacBook Microphone",
        ]

        for preferred in preferred_names:
            for index, device in enumerate(
                devices
            ):
                if (
                    preferred.lower()
                    in str(device["name"]).lower()
                    and device["max_input_channels"] > 0
                ):
                    return index

        default_input = sd.default.device[0]

        if (
            default_input is not None
            and int(default_input) >= 0
        ):
            return int(default_input)

        for index, device in enumerate(
            devices
        ):
            if device["max_input_channels"] > 0:
                return index

        return None


microphone_manager = MicrophoneManager()