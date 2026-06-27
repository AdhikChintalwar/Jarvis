import ollama

MODEL = "llama3.2:3b"


def choose_best_youtube_video(titles: str) -> str:

    prompt = f"""
You are an AI assistant.

Given these YouTube titles:

{titles}

Choose the best video for a beginner.

Explain why in one short sentence.

Return plain text only.
"""

    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"].strip()