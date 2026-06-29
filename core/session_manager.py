import time

from voice.streaming_asr import listen_streaming
from core.task_splitter import split_tasks
from brain.coordinator import coordinate_task
from core.executor import execute_tool_decision
from core.event_bus import publish


SESSION_TIMEOUT_SECONDS = 60


def should_stop(command_text: str) -> bool:
    text = command_text.lower()
    return (
        "stop baby" in text
        or "exit baby" in text
        or "sleep baby" in text
        or "stop jarvis" in text
        or "exit jarvis" in text
    )


def is_valid_command(text: str) -> bool:
    if not text:
        return False

    text = text.strip().lower()
    text = text.replace(".", "").replace(",", "").replace("!", "").replace("?", "")

    bad_commands = [
        "the", "a", "an", "also", "and", "or",
        "uh", "um", "hmm", "okay", "ok", "yeah", "yes",
        "thanks", "thank you", "bye", "you", "'s"
    ]

    if text in bad_commands:
        return False

    if len(text.split()) < 2:
        return False

    return True


def start_session(speak):
    publish("session_started")
    speak("Yes")
    print("Baby session started.")

    last_activity = time.time()

    while True:
        print("Listening in active session...")
        time.sleep(0.4)

        command_text = listen_streaming()
        print("Heard command:", command_text)

        publish("speech_recognized", {"text": command_text})

        if should_stop(command_text):
            publish("session_ended")
            speak("Going to sleep")
            print("Baby session ended.")
            return

        if not is_valid_command(command_text):
            print("Ignored empty/noisy command.")

            if time.time() - last_activity > SESSION_TIMEOUT_SECONDS:
                publish("session_ended")
                speak("Going to sleep")
                print("Session timed out.")
                return

            continue

        last_activity = time.time()

        try:
            tasks = split_tasks(command_text)
            publish("tasks_split", {"tasks": tasks})
            print("Split tasks:", tasks)

            for task in tasks:
                decision = coordinate_task(task)

                tool = decision.get("tool")
                target = decision.get("target")

                execute_tool_decision(tool, target, speak)
                time.sleep(2.0)

        except Exception as e:
            publish("error", {"message": str(e)})
            print("Error while executing command:", e)
            speak("Something went wrong")

        print("Ready for next command.")