import os

from core.wake_engine import OpenWakeWordEngine
from core.session_manager import start_session


def speak(text: str):
    os.system(f'say "{text}"')


def start_baby():
    wake_engine = OpenWakeWordEngine()

    speak("Baby is ready")

    try:
        while True:
            wake_engine.wait_for_wake_word()
            start_session(speak)
            print("Session closed. Returning to wake mode.")

    finally:
        wake_engine.close()


if __name__ == "__main__":
    start_baby()