import time

from core.offline_listener import listen_offline
from core.executor import execute_command


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

    if len(text) < 3:
        return False

    return text not in ["thank you", "thanks", "bye", "you", ".", ","]


def start_session(speak):
    speak("Yes")
    print("Baby session started.")

    last_activity = time.time()

    while True:
        print("Listening in active session...")

        command_text = listen_offline()
        print("Heard command:", command_text)

        if should_stop(command_text):
            speak("Going to sleep")
            print("Baby session ended.")
            return

        if not is_valid_command(command_text):
            print("Ignored empty/noisy command.")

            if time.time() - last_activity > SESSION_TIMEOUT_SECONDS:
                speak("Going to sleep")
                print("Session timed out.")
                return

            continue

        last_activity = time.time()

        try:
            execute_command(command_text, speak)
        except Exception as e:
            print("Error while executing command:", e)
            speak("Something went wrong")

        print("Ready for next command.")