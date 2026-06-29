import json
import ollama

MODEL = "qwen3:30b"


def fast_route(task: str):
    text = task.lower()

    desktop_words = [
        "open vs code", "open vscode", "open chrome", "open terminal",
        "open finder", "open app", "open folder", "open project",
        "coding setup", "ai setup", "research setup",
        "battery", "cpu", "disk", "screenshot", "screen",
        "lock mac", "what time"
    ]

    browser_words = [
        "youtube", "google", "search", "videos", "video",
        "tutorial", "tutorials", "website", "documentation",
        "docs", "news", "online"
    ]

    coding_words = [
        "debug", "fix this code", "write code", "python function",
        "react component", "sql query", "explain this code",
        "coding error", "programming"
    ]

    memory_words = [
        "remember", "forget", "what do you remember",
        "my preference", "preferences"
    ]

    if any(word in text for word in memory_words):
        return "memory"

    if any(word in text for word in browser_words):
        return "browser"

    if any(word in text for word in desktop_words):
        return "desktop"

    if any(word in text for word in coding_words):
        return "coding"

    return None


def extract_json(text: str):
    start = text.find("{")
    end = text.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError("No JSON found")

    return json.loads(text[start:end])


def choose_agent(task: str) -> str:
    fast_agent = fast_route(task)

    if fast_agent:
        print("FAST ROUTER:", fast_agent)
        return fast_agent

    prompt = f"""
You are Baby's intelligent Router.

Choose ONE agent.

Available agents:
- desktop
- browser
- coding
- memory
- planner

desktop:
Computer control, apps, folders, projects, profiles, screenshots, battery, CPU, disk, time.

browser:
Internet, Google, YouTube, videos, tutorials, websites, documentation, online research.

coding:
Writing code, debugging code, explaining code, GitHub, programming questions.

memory:
Remembering, forgetting, preferences, long-term memory.

planner:
Complex planning or anything unclear.

Return ONLY JSON.

Example:
{{
  "agent": "browser"
}}

Task:
{task}
"""

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    raw = response["message"]["content"].strip()

    print("LLM ROUTER:", raw)

    try:
        return extract_json(raw)["agent"]
    except Exception:
        return "planner"