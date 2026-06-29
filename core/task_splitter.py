import json
import ollama

MODEL = "qwen3:30b"


def extract_json(content: str) -> dict:
    start = content.find("{")
    end = content.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError("No JSON found")

    return json.loads(content[start:end])


def split_tasks(user_text: str) -> list[str]:
    prompt = f"""
You are Baby's task splitter.

Your job:
Split the user's command into separate independent tasks.

Rules:
- Return ONLY valid JSON.
- If the command contains one task, return one task.
- If the command contains multiple tasks joined by "and", "then", "also", or commas, split them.
- Do NOT change the meaning.
- Do NOT invent tasks.
- Keep each task short and executable.
- Preserve important words like app names, project names, websites, topics, and dates.

Return format:
{{
  "tasks": [
    "task one",
    "task two"
  ]
}}

Examples:

User:
Open VS Code and find me good Python videos

Return:
{{
  "tasks": [
    "Open VS Code",
    "Find me good Python videos"
  ]
}}

User:
Open my coding setup then search YouTube for LangGraph tutorials

Return:
{{
  "tasks": [
    "Open my coding setup",
    "Search YouTube for LangGraph tutorials"
  ]
}}

User:
What time is it

Return:
{{
  "tasks": [
    "What time is it"
  ]
}}

Now split this command:

{user_text}
"""

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    content = response["message"]["content"].strip()
    print("RAW TASK SPLIT:", content)

    try:
        data = extract_json(content)
        tasks = data.get("tasks", [])

        if not tasks:
            return [user_text]

        return tasks

    except Exception:
        return [user_text]