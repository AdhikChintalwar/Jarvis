import json
import ollama

MODEL = "qwen3:30b"


def extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError("No JSON found")

    return json.loads(text[start:end])


def decide_desktop_action(task: str) -> dict:
    prompt = f"""
You are Baby's Desktop Agent.

Convert the task into ONE tool call.

Allowed tools:
- open_app
- open_folder
- open_project
- run_profile
- take_screenshot
- take_and_open_screenshot
- analyze_screen
- analyze_screen_vision
- battery_status
- current_time
- disk_space
- cpu_usage
- lock_mac

Return ONLY JSON.

Do not use analyze_screen unless the user explicitly asks:
- what do you see
- analyze my screen
- read this error
- explain this screen
- screenshot

Format:
{{
  "tool": "tool_name",
  "target": "target value"
}}

Examples:

Task: Open VS Code
{{
  "tool": "open_app",
  "target": "Visual Studio Code"
}}

Task: Open my coding setup
{{
  "tool": "run_profile",
  "target": "coding"
}}

Task: Open Jarvis project
{{
  "tool": "open_project",
  "target": "jarvis"
}}

Task: What time is it
{{
  "tool": "current_time",
  "target": "time"
}}

Now convert this task:

{task}
"""

    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response["message"]["content"].strip()
    print("DESKTOP AGENT:", raw)

    try:
        return extract_json(raw)
    except Exception:
        return {"tool": "open_app", "target": task}