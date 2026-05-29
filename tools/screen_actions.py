import subprocess
from pathlib import Path
from datetime import datetime

SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def take_screenshot() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = SCREENSHOT_DIR / f"screenshot_{timestamp}.png"

    subprocess.run(
        ["screencapture", "-x", str(screenshot_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return str(screenshot_path)


def take_and_open_screenshot() -> str:
    path = take_screenshot()
    subprocess.run(["open", path])
    return f"Screenshot saved and opened: {path}"


def analyze_screen() -> str:
    import pytesseract
    import ollama

    screenshot_path = take_screenshot()

    extracted_text = pytesseract.image_to_string(
        screenshot_path,
        lang="eng"
    )

    if not extracted_text.strip():
        return "I took a screenshot, but I could not read any clear text from the screen."

    prompt = f"""
You are Jarvis, a helpful Mac desktop assistant.

The user asked you to analyze their screen.

Text extracted from the screenshot:

{extracted_text}

Explain what is on the screen in simple words.
If there is an error, explain the likely cause and what the user should do next.
"""

    response = ollama.chat(
        model="llama3.2:3b",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response["message"]["content"]