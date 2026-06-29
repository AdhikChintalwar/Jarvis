import asyncio

from core.memory_store import save_memory, get_last_command
from core.ollama_brain import understand_command
from core.planner import create_plan
from core.agent_loop import decide_next_step
from mcp_layer.mcp_client import call_mcp_tool
from core.tool_registry import get_registered_tool
from core.event_bus import publish


VALID_ACTIONS = {
    "open_app", "open_website", "open_folder", "run_profile",
    "repeat_last", "search_google", "search_youtube",
    "battery_status", "current_time", "disk_space", "cpu_usage",
    "lock_mac", "take_screenshot", "take_and_open_screenshot",
    "analyze_screen", "analyze_screen_vision", "planner",
    "open_project"
}

def execute_tool_decision(tool: str, target: str, speak):
    registered_tool = get_registered_tool(tool)

    if registered_tool:
        spoken = registered_tool.get("spoken")
        mcp_tool = registered_tool["mcp_tool"]
        arg_name = registered_tool.get("arg_name")

        if spoken:
            if target:
                speak(f"{spoken} {target}")
            else:
                speak(spoken)

        if arg_name:
            arguments = {arg_name: target}
        else:
            arguments = {}

        publish(
            "tool_started",
            {
                "tool": tool,
                "target": target
            }
        )

        result = run_mcp(mcp_tool, arguments)

        publish(
        "tool_finished",
            {
                "tool": tool,
                "target": target
            }
        )
        print(result)

        if tool in ["get_youtube_video_details", "get_youtube_titles"]:
            observation = result.content[0].text

            print("\nObservation:")
            print(observation)

            next_step = decide_next_step(target, observation)

            print("\nNext Step:")
            print(next_step)

            next_action = next_step.get("action")
            next_target = next_step.get("target")

            if next_action == "final_answer":

                spoken_text = next_target

                if "URL:" in spoken_text:
                    spoken_text = spoken_text.split("URL:")[0].strip()
                    spoken_text += ". I've opened it for you."

                speak(spoken_text)

                print("\nFinal Answer:")
                print(next_target)

                if "URL:" in next_target:
                    url = next_target.split("URL:")[-1].strip()
                    run_mcp("jarvis_open_url", {"url": url})

                return result

        if registered_tool.get("speak_result"):
            result_text = result.content[0].text
            speak(result_text[:250])
            print(result_text)

        if registered_tool.get("remember"):
            save_memory(tool, target)

        return result

    if tool == "planner":
        return execute_command(target, speak)

    print(f"Unknown tool decision: {tool}")
    speak("I do not know how to do that yet.")
    return None

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
            publish(
                "planner_step_started",
                {
                    "tool": tool,
                    "target": step_target
                }
            )

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
        publish(
            "planner_completed",
            {
                "tool": step.get("tool"),
                "target": step.get("target")
            }
        )
        return

    if action == "repeat_last":
        last = get_last_command()
        action = last.get("last_action")
        target = last.get("last_target")

        if not action or not target:
            speak("I do not have anything to repeat")
            return

    registered_tool = get_registered_tool(action)

    if registered_tool:
        spoken = registered_tool.get("spoken")
        mcp_tool = registered_tool["mcp_tool"]
        arg_name = registered_tool.get("arg_name")

        if spoken:
            if target:
                speak(f"{spoken} {target}")
            else:
                speak(spoken)

        if arg_name:
            arguments = {arg_name: target}
        else:
            arguments = {}

        result = run_mcp(mcp_tool, arguments)

        print(result)

        if registered_tool.get("speak_result"):
            result_text = result.content[0].text
            speak(result_text)
            print(result_text)

        if registered_tool.get("remember"):
            save_memory(action, target)

        return