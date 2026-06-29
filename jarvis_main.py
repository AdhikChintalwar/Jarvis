from voice.tts import speak
from voice.wake_engine import OpenWakeWordEngine
from core.session_manager import start_session
from core.event_handlers import register_event_handlers
from core.event_bus import publish


def start_baby():
    wake_engine = OpenWakeWordEngine()

    register_event_handlers()

    speak("I'm back Baby")
    publish("app_started")

    try:
        while True:
            wake_engine.wait_for_wake_word()

            publish("wake_detected")

            start_session(speak)

            print("Session closed. Returning to wake mode.")

    finally:
        publish("app_closed")
        wake_engine.close()


if __name__ == "__main__":
    start_baby()