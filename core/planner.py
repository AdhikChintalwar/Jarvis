import json
import ollama

MODEL = "llama3.2:3b"


def create_plan(goal: str) -> dict:
    prompt = f"""
You are a planner for a local Mac AI assistant named Jarvis.

Return ONLY valid JSON.

You can create a multi-step plan using these tools:

Available tools:
- search_google
- search_youtube
- analyze_screen_vision
- take_screenshot
- open_website
- open_app
- battery_status
- current_time
- disk_space
- cpu_usage

Rules:
- Keep plans short.
- Use only 1 to 3 steps.
- Do not invent tools.
- Do not use risky actions.
- Each step must have "tool" and "target".
- Return JSON only.

Example:
User goal: Find LangGraph tutorials on YouTube

{{
  "plan": [
    {{
      "tool": "search_youtube",
      "target": "LangGraph tutorials"
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
        return json.loads(content)
    except Exception:
        return {
            "plan": [
                {
                    "tool": "search_google",
                    "target": goal
                }
            ]
        }