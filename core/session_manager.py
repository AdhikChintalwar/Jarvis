from __future__ import annotations

import re
import time

from brain.coordinator import coordinate_task
from core.event_bus import publish
from core.executor import execute_tool_decision
from core.task_splitter import split_tasks
from voice.streaming_asr import listen_streaming


SESSION_TIMEOUT_SECONDS = 60

MAX_CONSECUTIVE_SILENCE_TIMEOUTS = 3

VALIDATION_PUNCTUATION = re.compile(
    r"[^\w\s']+",
    re.UNICODE,
)


BAD_COMMANDS = {
    "",
    "the",
    "a",
    "an",
    "also",
    "and",
    "or",
    "uh",
    "um",
    "hmm",
    "hm",
    "okay",
    "ok",
    "yeah",
    "thanks",
    "thank you",
    "bye",
    "you",
}


def should_stop(
    command_text: str,
) -> bool:
    if not command_text:
        return False

    text = (
        command_text
        .strip()
        .lower()
    )

    stop_phrases = {
        "stop baby",
        "exit baby",
        "sleep baby",
        "stop jarvis",
        "exit jarvis",
        "go to sleep",
        "go back to sleep",
    }

    return any(
        phrase in text
        for phrase in stop_phrases
    )


def normalize_for_validation(
    text: str,
) -> str:
    normalized = (
        text
        .strip()
        .lower()
    )

    normalized = (
        VALIDATION_PUNCTUATION.sub(
            "",
            normalized,
        )
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()

    return normalized


def is_valid_command(
    text: str,
) -> bool:
    if not text:
        return False

    normalized = (
        normalize_for_validation(
            text
        )
    )

    if normalized in BAD_COMMANDS:
        return False

    if len(normalized) < 2:
        return False

    return True


def start_session(
    speak,
) -> None:
    publish(
        "session_started",
        {},
    )

    print(
        "Baby session started."
    )

    last_activity = (
        time.monotonic()
    )

    consecutive_silence = 0

    while True:

        inactive_for = (
            time.monotonic()
            - last_activity
        )

        if (
            inactive_for
            >= SESSION_TIMEOUT_SECONDS
        ):
            publish(
                "session_ended",
                {
                    "reason": "timeout",
                },
            )

            print(
                "Session timed out."
            )

            return

        print(
            "Listening in active session..."
        )

        publish(
            "asr_listening",
            {},
        )

        command_text = (
            listen_streaming()
        )

        print(
            "Heard command:",
            command_text,
        )

        # =====================================================
        # Silence
        # =====================================================

        if not command_text:
            consecutive_silence += 1

            print(
                "No usable speech detected.",
                f"({consecutive_silence}/"
                f"{MAX_CONSECUTIVE_SILENCE_TIMEOUTS})",
            )

            if (
                consecutive_silence
                >= MAX_CONSECUTIVE_SILENCE_TIMEOUTS
            ):
                publish(
                    "session_ended",
                    {
                        "reason": "silence",
                    },
                )

                print(
                    "No more commands. "
                    "Returning to wake mode."
                )

                return

            continue

        # We heard something.
        consecutive_silence = 0

        publish(
            "speech_recognized",
            {
                "text": command_text,
            },
        )

        # =====================================================
        # Sleep command
        # =====================================================

        if should_stop(
            command_text
        ):
            publish(
                "session_ended",
                {
                    "reason": "voice_command",
                },
            )

            speak(
                "Going to sleep"
            )

            print(
                "Baby session ended."
            )

            return

        # =====================================================
        # Garbage / fillers
        # =====================================================

        if not is_valid_command(
            command_text
        ):
            print(
                "Ignored noisy command."
            )

            continue

        last_activity = (
            time.monotonic()
        )

        # =====================================================
        # Execute
        # =====================================================

        try:
            tasks = split_tasks(
                command_text
            )

            if not tasks:
                print(
                    "No actionable tasks found."
                )

                continue

            publish(
                "tasks_split",
                {
                    "tasks": tasks,
                },
            )

            print(
                "Split tasks:",
                tasks,
            )

            for task in tasks:

                if (
                    not isinstance(
                        task,
                        str,
                    )
                    or not task.strip()
                ):
                    continue

                publish(
                    "task_started",
                    {
                        "task": task,
                    },
                )

                decision = (
                    coordinate_task(
                        task
                    )
                )

                if not isinstance(
                    decision,
                    dict,
                ):
                    raise TypeError(
                        "Coordinator must "
                        "return a dictionary."
                    )

                tool = (
                    decision.get(
                        "tool"
                    )
                )

                target = (
                    decision.get(
                        "target"
                    )
                )

                if not tool:
                    print(
                        "Coordinator returned "
                        "no tool."
                    )

                    continue

                execute_tool_decision(
                    tool,
                    target,
                    speak,
                )

                publish(
                    "task_finished",
                    {
                        "task": task,
                        "tool": tool,
                    },
                )

                # Short guard against Baby hearing tool/TTS audio.
                time.sleep(
                    0.25
                )

        except Exception as error:
            publish(
                "error",
                {
                    "message": str(
                        error
                    ),
                },
            )

            print(
                "Error while executing command:",
                error,
            )

            speak(
                "Something went wrong"
            )

        print(
            "Ready for next command."
        )