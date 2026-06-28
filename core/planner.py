import json
import ollama

MODEL = "qwen3:30b"

from core.tool_registry import get_tool_descriptions

tool_text = get_tool_descriptions()
def extract_json(content: str) -> dict:
    start = content.find("{")
    end = content.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError("No JSON found")

    return json.loads(content[start:end])


def create_plan(goal: str) -> dict:
    prompt = f"""

You are a planner for a local Mac AI assistant named Baby.
Return ONLY valid JSON.

Important tool rules:
- YouTube is not a Mac app.
- Google is not a Mac app.
- Do not use open_app for YouTube, Google, websites, or web searches.
- For YouTube video requests, use get_youtube_video_details or get_youtube_titles.
- For opening YouTube search results, use search_youtube.
- For Google/web research, use search_google.

Available tools:

{tool_text}

Rules:
- Keep plans short.
- Use only 1 to 3 steps.
- Do not invent tools.
- Do not use risky actions.
- Each step must have "tool" and "target".
- Return JSON only.
- For YouTube video recommendations, first use get_youtube_titles.
- For setup/profile requests, use run_profile.
- Do not use analyze_screen_vision unless the user asks about the screen.

For YouTube video recommendations, prefer get_youtube_video_details over get_youtube_titles.

For any request that says "find me good videos", "best videos", "recommend videos", or "good tutorials", DO NOT use search_youtube first.
Use get_youtube_video_details if available.
If get_youtube_video_details is not available, use get_youtube_titles.
Use search_youtube only when the user explicitly says "search YouTube for X" or "open YouTube".

Never return an empty target. Every step target must be meaningful.
For get_youtube_video_details, the target must be the video search query.
For "find good Python videos", use target "Python beginner tutorial".
Do not use search_google before get_youtube_video_details for YouTube/video requests.


Example:
User goal: Find LangGraph tutorials on YouTube

{{
  "plan": [
    {{
      "tool": "get_youtube_titles",
      "target": "LangGraph tutorial"
    }}
  ]
}}

Example:
User goal: Research dopamine transporter papers

{{
  "plan": [
    {{
      "tool": "search_google",
      "target": "dopamine transporter research papers"
    }}
  ]
}}

Example:
User goal: Open my coding setup

{{
  "plan": [
    {{
      "tool": "run_profile",
      "target": "coding"
    }}
  ]
}}

Example:
User goal: Find good Python videos

{{
  "plan": [
    {{
      "tool": "get_youtube_video_details",
      "target": "Python beginner tutorial"
    }}
  ]
}}

Example:
User goal: Find good Python videos

{{
  "plan": [
    {{
      "tool": "get_youtube_titles",
      "target": "Python beginner tutorial"
    }}
  ]
}}

Now create a plan for this goal:

{goal}
"""

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    content = response["message"]["content"].strip()

    print("RAW PLAN:", content)

    try:
        return extract_json(content)
    except Exception:
        return {
            "plan": [
                {
                    "tool": "search_google",
                    "target": goal
                }
            ]
        }