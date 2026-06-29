import json
import ollama

MODEL = "qwen3:30b"


def extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError("No JSON found")

    return json.loads(text[start:end])


def decide_browser_action(task: str) -> dict:
    prompt = f"""
You are Baby's Browser Agent.

Convert the task into ONE browser/research tool call.

Allowed tools:
- search_google
- search_youtube
- get_youtube_titles
- get_youtube_video_details
- open_website

Rules:
- If the user wants recommendations for good/best videos, use get_youtube_video_details.
- If the user says search YouTube, use search_youtube.
- If the user says search Google, use search_google.
- If the user says open a website, use open_website.
- Do not invent tools.

Return ONLY JSON.

Format:
{{
  "tool": "tool_name",
  "target": "target value"
}}

Examples:

Task: Find me good Python videos
{{
  "tool": "get_youtube_video_details",
  "target": "Python beginner tutorial"
}}

Task: Search YouTube for LangGraph tutorials
{{
  "tool": "search_youtube",
  "target": "LangGraph tutorials"
}}

Task: Search Google for dopamine transporter papers
{{
  "tool": "search_google",
  "target": "dopamine transporter papers"
}}

Now convert this task:

{task}
"""

    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response["message"]["content"].strip()
    print("BROWSER AGENT:", raw)

    try:
        return extract_json(raw)
    except Exception:
        return {"tool": "search_google", "target": task}