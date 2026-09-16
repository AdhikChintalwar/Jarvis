from __future__ import annotations

import re
import time
from collections import deque
from pathlib import Path

import numpy as np
import sherpa_onnx

from core.event_bus import publish
from voice.microphone_manager import (
    SAMPLE_RATE,
    microphone_manager,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_DIR = (
    PROJECT_ROOT
    / "models"
    / "sensevoice"
    / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"
)


# ---------------------------------------------------------
# Listener tuning
# ---------------------------------------------------------

NOISE_CALIBRATION_SECONDS = 0.20
MAX_THRESHOLD = 0.009
MIN_THRESHOLD = 0.0045
THRESHOLD_MULTIPLIER = 2.0

SPEECH_START_FRAMES = 2

END_SILENCE_SECONDS = 0.42
MAX_WAIT_FOR_SPEECH_SECONDS = 6.0
MAX_UTTERANCE_SECONDS = 15.0
MIN_UTTERANCE_SECONDS = 0.25

PRE_ROLL_SECONDS = 0.30

_RECOGNIZER = None


# ---------------------------------------------------------
# Garbage / hallucination rejection
# ---------------------------------------------------------

CJK_PATTERN = re.compile(
    r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]"
)

ALPHANUMERIC_PATTERN = re.compile(
    r"[A-Za-z0-9]"
)

WORD_PATTERN = re.compile(
    r"[A-Za-z]+(?:'[A-Za-z]+)?"
)

NOISE_ONLY = {
    "",
    ".",
    ",",
    "?",
    "!",
    "uh",
    "um",
    "hmm",
    "hm",
    "ah",
    "oh",
}


def create_recognizer():
    global _RECOGNIZER

    if _RECOGNIZER is not None:
        return _RECOGNIZER

    print("Loading SenseVoice model...")

    _RECOGNIZER = (
        sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(
                MODEL_DIR
                / "model.int8.onnx"
            ),
            tokens=str(
                MODEL_DIR
                / "tokens.txt"
            ),
            num_threads=8,
            use_itn=True,
            language="en",
            debug=False,
        )
    )

    print("SenseVoice model ready.")

    return _RECOGNIZER


def _seconds_for_samples(
    sample_count: int,
) -> float:
    return sample_count / SAMPLE_RATE


def _calculate_threshold(
    noise_levels: list[float],
) -> float:
    if not noise_levels:
        return MIN_THRESHOLD

    noise_floor = float(
        np.median(noise_levels)
    )

    calculated = max(
        MIN_THRESHOLD,
        noise_floor * THRESHOLD_MULTIPLIER,
    )

    return min(
        calculated,
        MAX_THRESHOLD,
    )


def record_utterance() -> np.ndarray:
    """
    Capture one spoken utterance from the shared mic.

    The stream stays open permanently.
    """

    microphone_manager.start()

    # Drop stale frames from wake-word mode.
    microphone_manager.clear()

    publish(
        "listener_state",
        {
            "state": "calibrating",
        },
    )

    noise_levels: list[float] = []

    calibration_started = time.monotonic()

    while (
        time.monotonic()
        - calibration_started
        < NOISE_CALIBRATION_SECONDS
    ):
        frame = microphone_manager.get_frame(
            timeout=0.2
        )

        if frame is not None:
            noise_levels.append(
                frame.rms
            )

    threshold = _calculate_threshold(
        noise_levels
    )

    print(
        f"Listener ready. "
        f"Threshold={threshold:.5f}"
    )

    publish(
        "listener_state",
        {
            "state": "listening",
            "threshold": threshold,
        },
    )

    pre_roll_max_frames = max(
        1,
        int(
            PRE_ROLL_SECONDS
            / (
                microphone_manager.blocksize
                / SAMPLE_RATE
            )
        ),
    )

    pre_roll = deque(
        maxlen=pre_roll_max_frames
    )

    utterance_chunks: list[
        np.ndarray
    ] = []

    speech_started = False

    consecutive_speech_frames = 0

    listener_started = time.monotonic()

    speech_started_at: float | None = None
    last_voice_at: float | None = None

    while True:
        frame = microphone_manager.get_frame(
            timeout=0.5
        )

        now = time.monotonic()

        if frame is None:
            if (
                not speech_started
                and now
                - listener_started
                >= MAX_WAIT_FOR_SPEECH_SECONDS
            ):
                publish(
                    "speech_timeout",
                    {},
                )
                return np.array(
                    [],
                    dtype=np.float32,
                )

            continue

        is_voice = (
            frame.rms >= threshold
        )

        if not speech_started:
            pre_roll.append(
                frame.samples
            )

            if is_voice:
                consecutive_speech_frames += 1

                if (
                    consecutive_speech_frames
                    >= SPEECH_START_FRAMES
                ):
                    speech_started = True
                    speech_started_at = now
                    last_voice_at = now

                    utterance_chunks.extend(
                        list(pre_roll)
                    )

                    print("Speech detected.")

                    publish(
                        "speech_started",
                        {},
                    )

            else:
                consecutive_speech_frames = 0

            if (
                now - listener_started
                >= MAX_WAIT_FOR_SPEECH_SECONDS
            ):
                print(
                    "No speech detected."
                )

                publish(
                    "speech_timeout",
                    {},
                )

                return np.array(
                    [],
                    dtype=np.float32,
                )

            continue

        # Speech already started.
        utterance_chunks.append(
            frame.samples
        )

        if is_voice:
            last_voice_at = now

        speech_duration = (
            now
            - speech_started_at
            if speech_started_at
            else 0.0
        )

        silence_duration = (
            now
            - last_voice_at
            if last_voice_at
            else 0.0
        )

        if (
            speech_duration
            >= MIN_UTTERANCE_SECONDS
            and silence_duration
            >= END_SILENCE_SECONDS
        ):
            break

        if (
            speech_duration
            >= MAX_UTTERANCE_SECONDS
        ):
            print(
                "Maximum utterance "
                "duration reached."
            )
            break

    if not utterance_chunks:
        return np.array(
            [],
            dtype=np.float32,
        )

    audio = np.concatenate(
        utterance_chunks
    ).astype(
        np.float32,
        copy=False,
    )

    duration = _seconds_for_samples(
        len(audio)
    )

    publish(
        "speech_ended",
        {
            "duration": duration,
        },
    )

    if duration < MIN_UTTERANCE_SECONDS:
        return np.array(
            [],
            dtype=np.float32,
        )

    return audio


def transcribe(
    audio: np.ndarray,
) -> str:
    if audio.size == 0:
        return ""

    recognizer = create_recognizer()

    publish(
        "asr_processing",
        {},
    )

    stream = recognizer.create_stream()

    stream.accept_waveform(
        SAMPLE_RATE,
        audio,
    )

    recognizer.decode_stream(
        stream
    )

    text = (
        stream.result.text
        or ""
    ).strip()

    text = clean_transcription(
        text
    )

    if not is_usable_transcription(
        text
    ):
        publish(
            "speech_rejected",
            {
                "text": text,
                "reason": (
                    "low_quality_transcription"
                ),
            },
        )

        print(
            "Rejected transcription:",
            repr(text),
        )

        return ""

    publish(
        "speech_final",
        {
            "text": text,
        },
    )

    print(
        "Final:",
        text,
    )

    return text


def clean_transcription(
    text: str,
) -> str:
    if not text:
        return ""

    cleaned = text.strip()

    # SenseVoice sometimes adds CJK punctuation.
    cleaned = (
        cleaned
        .replace("。", ".")
        .replace("？", "?")
        .replace("！", "!")
        .replace("，", ",")
    )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    ).strip()

    return cleaned


def is_usable_transcription(
    text: str,
) -> bool:
    if not text:
        return False

    normalized = (
        text
        .strip()
        .lower()
    )

    normalized = normalized.strip(
        " .,!?:;"
    )

    if normalized in NOISE_ONLY:
        return False

    # English lock:
    # reject obvious Chinese/Japanese/Korean hallucination.
    if CJK_PATTERN.search(text):
        return False

    if not ALPHANUMERIC_PATTERN.search(
        text
    ):
        return False

    words = WORD_PATTERN.findall(
        text
    )

    # Allow useful one-word commands.
    if len(words) == 1:
        word = words[0].lower()

        useful_single_words = {
            "stop",
            "sleep",
            "exit",
            "pause",
            "continue",
            "cancel",
            "yes",
            "no",
        }

        return (
            word
            in useful_single_words
            or len(word) >= 4
        )

    return True


def listen_sensevoice() -> str:
    audio = record_utterance()

    if audio.size == 0:
        return ""

    return transcribe(
        audio
    )


# Warm up model once.
create_recognizer()