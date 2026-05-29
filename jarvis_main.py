import os
import time
import asyncio
import pyaudio
import numpy as np
from openwakeword.model import Model
from core.memory_store import save_memory, get_last_command

from core.offline_listener import listen_offline
from core.ollama_brain import understand_command
from mcp_layer.mcp_client import call_mcp_tool
from core.planner import create_plan

WAKE_THRESHOLD = 0.65
COOLDOWN_SECONDS = 2


def speak(text: str):
    os.system(f'say "{text}"')


def is_valid_command(text: str) -> bool:
    if not text:
        return False

    text = text.strip().lower()

    if len(text) < 3:
        return False

    bad_phrases = [
        "thank you",
        "thanks",
        "bye",
        "you",
        ".",
        ","
    ]

    if text in bad_phrases:
        return False

    return True


def handle_command(text: str):
    print("Command:", text)

    if not is_valid_command(text):
        print("Ignored empty/noisy command.")
        return

    parsed = understand_command(text)
    print("Ollama understood:", parsed)

    action = parsed.get("action")
    target = parsed.get("target")

    if action == "planner":
        speak("Creating a plan")
        plan_data = create_plan(target)

        print("Plan:", plan_data)

        steps = plan_data.get("plan", [])

        if not steps:
            speak("I could not create a plan")
            return

        speak(f"I found {len(steps)} step plan")

        for step in steps:
            tool = step.get("tool")
            step_target = step.get("target")

            print(f"Executing step: {tool} -> {step_target}")

            if tool == "search_google":
                speak(f"Searching Google for {step_target}")
                result = asyncio.run(
                    call_mcp_tool("jarvis_search_google", {"query": step_target})
                )
                print(result)

            elif tool == "search_youtube":
                speak(f"Searching YouTube for {step_target}")
                result = asyncio.run(
                    call_mcp_tool("jarvis_search_youtube", {"query": step_target})
                )
                print(result)

            elif tool == "open_website":
                speak(f"Opening {step_target}")
                result = asyncio.run(
                    call_mcp_tool("jarvis_open_website", {"site_or_url": step_target})
                )
                print(result)

            elif tool == "open_app":
                speak(f"Opening {step_target}")
                result = asyncio.run(
                    call_mcp_tool("jarvis_open_app", {"app_name": step_target})
                )
                print(result)

            elif tool == "take_screenshot":
                speak("Taking screenshot")
                result = asyncio.run(
                    call_mcp_tool("jarvis_take_screenshot", {})
                )
                print(result)

            elif tool == "analyze_screen_vision":
                speak("Analyzing screen")
                result = asyncio.run(
                    call_mcp_tool("jarvis_analyze_screen_vision", {})
                )
                print(result)

            elif tool == "battery_status":
                result = asyncio.run(
                    call_mcp_tool("jarvis_battery_status", {})
                )
                text = result.content[0].text
                speak(text)
                print(text)

            elif tool == "current_time":
                result = asyncio.run(
                    call_mcp_tool("jarvis_current_time", {})
                )
                text = result.content[0].text
                speak(text)
                print(text)

            elif tool == "disk_space":
                result = asyncio.run(
                    call_mcp_tool("jarvis_disk_space", {})
                )
                text = result.content[0].text
                speak(text)
                print(text)

            elif tool == "cpu_usage":
                result = asyncio.run(
                    call_mcp_tool("jarvis_cpu_usage", {})
                )
                text = result.content[0].text
                speak(text)
                print(text)

            else:
                print(f"Unknown planner tool skipped: {tool}")

        speak("Plan completed")
        return
    

    if action == "repeat_last":
        last = get_last_command()
        action = last.get("last_action")
        target = last.get("last_target")

        if not action or not target:
            speak("I do not have anything to repeat")
            return

    if action == "open_app":
        speak(f"Opening {target}")
        result = asyncio.run(
            call_mcp_tool("jarvis_open_app", {"app_name": target})
        )
        print(result)
        save_memory("open_app", target)

    elif action == "open_website":
        speak(f"Opening {target}")
        result = asyncio.run(
            call_mcp_tool("jarvis_open_website", {"site_or_url": target})
        )
        print(result)
        save_memory("open_website", target)

    elif action == "open_folder":
        speak("Opening folder")
        result = asyncio.run(
            call_mcp_tool("jarvis_open_folder", {"path": target})
        )
        print(result)
        save_memory("open_folder", target)

    elif action == "run_profile":
        speak(f"Starting {target} mode")
        result = asyncio.run(
            call_mcp_tool("jarvis_run_profile", {"profile_name": target})
        )
        print(result)
        save_memory("run_profile", target)

    elif action == "search_google":
        speak(f"Searching Google for {target}")
        result = asyncio.run(
            call_mcp_tool("jarvis_search_google", {"query": target})
        )
        print(result)

    elif action == "search_youtube":
        speak(f"Searching YouTube for {target}")
        result = asyncio.run(
            call_mcp_tool("jarvis_search_youtube", {"query": target})
        )
        print(result)

    elif action == "battery_status":
        result = asyncio.run(
            call_mcp_tool("jarvis_battery_status", {})
        )
        text = result.content[0].text
        speak(text)
        print(text)

    elif action == "current_time":
        result = asyncio.run(
            call_mcp_tool("jarvis_current_time", {})
        )
        text = result.content[0].text
        speak(text)
        print(text)

    elif action == "disk_space":
        result = asyncio.run(
            call_mcp_tool("jarvis_disk_space", {})
        )
        text = result.content[0].text
        speak(text)
        print(text)

    elif action == "cpu_usage":
        result = asyncio.run(
            call_mcp_tool("jarvis_cpu_usage", {})
        )
        text = result.content[0].text
        speak(text)
        print(text)

    elif action == "lock_mac":
        speak("Locking your Mac")
        result = asyncio.run(
            call_mcp_tool("jarvis_lock_mac", {})
        )
        print(result)

    elif action == "take_screenshot":
        speak("Taking screenshot")
        result = asyncio.run(
            call_mcp_tool("jarvis_take_screenshot", {})
        )
        text = result.content[0].text
        speak("Screenshot saved")
        print(text)

    elif action == "take_and_open_screenshot":
        speak("Taking screenshot")
        result = asyncio.run(
            call_mcp_tool("jarvis_take_and_open_screenshot", {})
        )
        text = result.content[0].text
        speak("Screenshot opened")
        print(text)

    elif action == "analyze_screen":
        speak("Analyzing your screen")
        result = asyncio.run(
            call_mcp_tool("jarvis_analyze_screen", {})
        )
        text = result.content[0].text
        print(text)
        speak(text[:250])

    elif action == "analyze_screen_vision":
        speak("Looking at your screen")
        result = asyncio.run(
            call_mcp_tool("jarvis_analyze_screen_vision", {})
        )

        text = result.content[0].text
        print(text)
        speak(text[:250])


    else:
        print("Unknown command ignored.")
        # Do not speak this every time, otherwise it becomes annoying


def start_jarvis():
    model = Model(
        wakeword_models=[],
        inference_framework="onnx"
    )

    CHUNK = 1280
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    audio = pyaudio.PyAudio()

    stream = audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    speak("Jarvis is ready")
    print("Waiting for wake word...")

    last_trigger_time = 0

    while True:
        audio_data = stream.read(CHUNK, exception_on_overflow=False)
        frame = np.frombuffer(audio_data, dtype=np.int16)

        prediction = model.predict(frame)

        for key, score in prediction.items():
            current_time = time.time()

            if score > WAKE_THRESHOLD and current_time - last_trigger_time > COOLDOWN_SECONDS:
                last_trigger_time = current_time

                print(f"Wake word detected: {key}")
                speak("Yes")

                time.sleep(0.5)

                command_text = listen_offline()
                print("Heard command:", command_text)

                if "stop jarvis" in command_text or "exit jarvis" in command_text:
                    speak("Jarvis stopped")
                    print("Jarvis stopped.")
                    return

                handle_command(command_text)

                print("Cooling down...")
                time.sleep(2)

                print("Waiting for wake word again...")


if __name__ == "__main__":
    start_jarvis()