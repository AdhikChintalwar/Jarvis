import json
import ollama

MODEL = "qwen3:30b"


def extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError("No JSON found")

    return json.loads(text[start:end])


def decide_coding_action(task: str) -> dict:
    prompt = f"""
You are Baby's Coding Agent.

Convert the user's coding task into ONE safe action.

Allowed tools for now:
- planner

Rules:
- Use planner for explaining code, debugging, architecture, errors, or coding help.
- Do NOT edit files yet.
- Do NOT run commands yet.
- Do NOT invent tools.

Return ONLY JSON.

Format:
{{
  "tool": "planner",
  "target": "clear coding request"
}}

Task:
{task}
"""

    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response["message"]["content"].strip()
    print("CODING AGENT:", raw)

    try:
        return extract_json(raw)
    except Exception:
        return {
            "tool": "planner",
            "target": task
        }