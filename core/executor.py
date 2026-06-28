import asyncio

from core.memory_store import save_memory, get_last_command
from core.ollama_brain import understand_command
from core.planner import create_plan
from core.agent_loop import decide_next_step
from mcp_layer.mcp_client import call_mcp_tool


VALID_ACTIONS = {
    "open_app", "open_website", "open_folder", "run_profile",
    "repeat_last", "search_google", "search_youtube",
    "battery_status", "current_time", "disk_space", "cpu_usage",
    "lock_mac", "take_screenshot", "take_and_open_screenshot",
    "analyze_screen", "analyze_screen_vision", "planner",
    "open_project"
}


def run_mcp(tool_name: str, arguments: dict):
    return asyncio.run(call_mcp_tool(tool_name, arguments))


def execute_command(text: str, speak):
    print("Command:", text)

    parsed = understand_command(text)
    print("Ollama understood:", parsed)

    action = parsed.get("action")
    target = parsed.get("target")

    if action not in VALID_ACTIONS:
        if any(word in text.lower() for word in ["find", "research", "plan", "compare", "investigate"]):
            action = "planner"
            target = text
        else:
            print("Unknown command ignored.")
            return

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

            if not step_target:
                step_target = target

            print(f"Executing step: {tool} -> {step_target}")

            if tool == "search_google":
                speak(f"Searching Google for {step_target}")
                result = run_mcp("jarvis_search_google", {"query": step_target})
                print(result)

            elif tool == "search_youtube":
                speak(f"Searching YouTube for {step_target}")
                result = run_mcp("jarvis_search_youtube", {"query": step_target})
                print(result)

            elif tool == "get_youtube_titles":
                speak(f"Checking YouTube results for {step_target}")
                result = run_mcp("jarvis_get_youtube_titles", {"query": step_target})
                observation = result.content[0].text

                print("\nObservation:")
                print(observation)

                next_step = decide_next_step(target, observation)
                print("\nNext Step:")
                print(next_step)

                next_action = next_step.get("action")
                next_target = next_step.get("target")

                if next_action == "final_answer":
                    speak(next_target)
                    print("\nFinal Answer:")
                    print(next_target)
                    return

            elif tool == "get_youtube_video_details":
                speak(f"Checking YouTube video details for {step_target}")
                result = run_mcp("jarvis_get_youtube_video_details", {"query": step_target})
                observation = result.content[0].text

                print("\nObservation:")
                print(observation)

                next_step = decide_next_step(target, observation)
                print("\nNext Step:")
                print(next_step)

                next_action = next_step.get("action")
                next_target = next_step.get("target")

                if next_action == "final_answer":
                    speak(next_target)
                    print("\nFinal Answer:")
                    print(next_target)

                    if "URL:" in next_target:
                        url = next_target.split("URL:")[-1].strip()
                        run_mcp("jarvis_open_url", {"url": url})

                    return

                elif next_action == "search_youtube":
                    speak(f"Searching YouTube for {next_target}")
                    result = run_mcp("jarvis_search_youtube", {"query": next_target})
                    print(result)

                elif next_action == "search_google":
                    speak(f"Searching Google for {next_target}")
                    result = run_mcp("jarvis_search_google", {"query": next_target})
                    print(result)

            elif tool == "open_website":
                speak(f"Opening {step_target}")
                result = run_mcp("jarvis_open_website", {"site_or_url": step_target})
                print(result)

            elif tool == "open_app":
                speak(f"Opening {step_target}")
                result = run_mcp("jarvis_open_app", {"app_name": step_target})
                print(result)

            elif tool == "run_profile":
                speak(f"Starting {step_target} mode")
                result = run_mcp("jarvis_run_profile", {"profile_name": step_target})
                print(result)

            elif tool == "open_project":
                speak(f"Opening {step_target} project")
                result = run_mcp("jarvis_open_project", {"project_name": step_target})
                print(result)

            elif tool == "take_screenshot":
                speak("Taking screenshot")
                result = run_mcp("jarvis_take_screenshot", {})
                print(result)

            elif tool == "analyze_screen_vision":
                speak("Analyzing screen")
                result = run_mcp("jarvis_analyze_screen_vision", {})
                print(result)

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
        result = run_mcp("jarvis_open_app", {"app_name": target})
        print(result)
        save_memory("open_app", target)

    elif action == "open_website":
        speak(f"Opening {target}")
        result = run_mcp("jarvis_open_website", {"site_or_url": target})
        print(result)
        save_memory("open_website", target)

    elif action == "open_folder":
        speak("Opening folder")
        result = run_mcp("jarvis_open_folder", {"path": target})
        print(result)
        save_memory("open_folder", target)

    elif action == "run_profile":
        speak(f"Starting {target} mode")
        result = run_mcp("jarvis_run_profile", {"profile_name": target})
        print(result)
        save_memory("run_profile", target)

    elif action == "open_project":
        speak(f"Opening {target} project")
        result = run_mcp("jarvis_open_project", {"project_name": target})
        print(result)

    elif action == "search_google":
        speak(f"Searching Google for {target}")
        result = run_mcp("jarvis_search_google", {"query": target})
        print(result)

    elif action == "search_youtube":
        speak(f"Searching YouTube for {target}")
        result = run_mcp("jarvis_search_youtube", {"query": target})
        print(result)

    elif action == "battery_status":
        result = run_mcp("jarvis_battery_status", {})
        result_text = result.content[0].text
        speak(result_text)
        print(result_text)

    elif action == "current_time":
        result = run_mcp("jarvis_current_time", {})
        result_text = result.content[0].text
        speak(result_text)
        print(result_text)

    elif action == "disk_space":
        result = run_mcp("jarvis_disk_space", {})
        result_text = result.content[0].text
        speak(result_text)
        print(result_text)

    elif action == "cpu_usage":
        result = run_mcp("jarvis_cpu_usage", {})
        result_text = result.content[0].text
        speak(result_text)
        print(result_text)

    elif action == "lock_mac":
        speak("Locking your Mac")
        result = run_mcp("jarvis_lock_mac", {})
        print(result)

    elif action == "take_screenshot":
        speak("Taking screenshot")
        result = run_mcp("jarvis_take_screenshot", {})
        result_text = result.content[0].text
        speak("Screenshot saved")
        print(result_text)

    elif action == "take_and_open_screenshot":
        speak("Taking screenshot")
        result = run_mcp("jarvis_take_and_open_screenshot", {})
        result_text = result.content[0].text
        speak("Screenshot opened")
        print(result_text)

    elif action == "analyze_screen":
        speak("Analyzing your screen")
        result = run_mcp("jarvis_analyze_screen", {})
        result_text = result.content[0].text
        print(result_text)
        speak(result_text[:250])

    elif action == "analyze_screen_vision":
        speak("Looking at your screen")
        result = run_mcp("jarvis_analyze_screen_vision", {})
        result_text = result.content[0].text
        print(result_text)
        speak(result_text[:250])

    else:
        print("Unknown command ignored.")