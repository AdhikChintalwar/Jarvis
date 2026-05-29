import os
from offline_listener import listen_offline
from mac_actions import open_app, open_website, open_folder, run_profile
from ollama_brain import understand_command
import asyncio
from mcp_client import call_mcp_tool

WAKE_WORD = "jarvis"


def speak(text: str):
    os.system(f'say "{text}"')


def listen_once() -> str:
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("Listening... say: Jarvis open YouTube")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source)

    try:
        return recognizer.recognize_google(audio).lower()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        return f"speech error: {e}"


def handle_command(text: str):
    print("You said:", text)

    if WAKE_WORD not in text:
        print("Wake word not detected.")
        return

    command = text.replace(WAKE_WORD, "").strip()

    if "start coding" in command or "coding mode" in command:
        speak("Starting coding mode")
        print(run_profile("coding"))
        return

    if "start study" in command or "study mode" in command:
        speak("Starting study mode")
        print(run_profile("study"))
        return

    if "start music" in command or "music mode" in command:
        speak("Starting music mode")
        print(run_profile("music"))
        return

    parsed = understand_command(text)
    print("Ollama understood:", parsed)

    action = parsed.get("action")
    target = parsed.get("target")

    if action == "open_app":
        speak(f"Opening {target}")
        result = asyncio.run(call_mcp_tool("jarvis_open_app", {"app_name": target}))
        print(result)

    elif action == "open_website":
        speak(f"Opening {target}")
        result = asyncio.run(call_mcp_tool("jarvis_open_website", {"site_or_url": target}))
        print(result)

    elif action == "open_folder":
        speak("Opening folder")
        result = asyncio.run(call_mcp_tool("jarvis_open_folder", {"path": target}))
        print(result)

    elif action == "run_profile":
        speak(f"Starting {target} mode")
        result = asyncio.run(
            call_mcp_tool(
                "jarvis_run_profile",
                {"profile_name": target}
            )
        )
        print(result)

    else:
        speak("I did not understand that command")
        print("I did not understand that command.")


if __name__ == "__main__":
    while True:
        text = listen_offline()

        if "stop jarvis" in text or "exit jarvis" in text:
            speak("Jarvis stopped")
            print("Jarvis stopped.")
            break

        handle_command(text)