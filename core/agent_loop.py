import json
import ollama

MODEL = "qwen3:30b"


def extract_json(content: str) -> dict:
    start = content.find("{")
    end = content.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError("No JSON found")

    return json.loads(content[start:end])


def decide_next_step(goal: str, observation: str) -> dict:
    prompt = f"""
You are Baby, a local AI agent.
The user goal is:
{goal}

You observed this result:
{observation}

Your job:
- If the observation contains YouTube titles and URLs, choose the best ONE video and include its URL in the final answer.
- Give a clear recommendation.
- Explain why in one short sentence.
- Do NOT just say "Top 5 videos found".
- Do NOT search again unless the titles are irrelevant.
- Return ONLY valid JSON.

Allowed actions:
- final_answer
- search_youtube
- search_google

Preferred response:
{{
  "action": "final_answer",
  "target": "I recommend '[exact video title]' because it looks beginner-friendly. URL: [exact URL]"
}}

If titles are irrelevant:
{{
  "action": "search_youtube",
  "target": "better search query"
}}

Now decide.
"""

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    content = response["message"]["content"].strip()
    print("RAW NEXT STEP:", content)

    try:
        return extract_json(content)
    except Exception:
        return {
            "action": "final_answer",
            "target": "I found results, but I could not confidently choose the best one."
        }