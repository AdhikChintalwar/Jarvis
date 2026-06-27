import json
import ollama

MODEL = "llama3.2:3b"

def extract_json(content: str) -> dict:
    start = content.find("{")
    end = content.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError("No JSON found")

    json_text = content[start:end]
    return json.loads(json_text)

def understand_command(user_text: str) -> dict:

    prompt = f"""
You are Baby, a personal AI assistant running on a Mac.

Return ONLY valid JSON.

Allowed actions:
- open_app
- open_website
- open_folder
- run_profile
- unknown
- repeat_last
- search_google
- search_youtube
- battery_status
- current_time
- disk_space
- cpu_usage
- lock_mac
- take_screenshot
- take_and_open_screenshot
- analyze_screen
- analyze_screen_vision
- planner
- open_project
- get_youtube_video_details

Examples:

If the user says "in YouTube", "on YouTube", or "YouTube for", use search_youtube, not open_website.
If the user says "in Google", "on Google", or "Google for", use search_google, not open_website.
Only use open_website when the user says open YouTube, open Google, open Gmail, etc.

If the user says "open YouTube and search for X", return search_youtube with target X.
If the user says "open Google and search for X", return search_google with target X.
Never return a separate query field. Only return action and target.
For YouTube video recommendations, prefer get_youtube_video_details over get_youtube_titles.
If the user asks to find, research, plan, investigate, compare, or do a multi-step task, return planner.

If the user says "my coding setup", "my AI setup", "my research setup", or "my study setup", always return run_profile.
Never use open_website for anything ending with "setup".

User: Jarvis open YouTube
{{"action": "open_website", "target": "youtube"}}

User: Jarvis open Chrome
{{"action": "open_app", "target": "chrome"}}

User: Jarvis open downloads
{{"action": "open_folder", "target": "~/Downloads"}}

User: Jarvis start coding
{{"action": "run_profile", "target": "coding"}}

User: Jarvis start study mode
{{"action": "run_profile", "target": "study"}}

User: Jarvis open it again
{{"action": "repeat_last", "target": "last"}}

User: Jarvis search Google for AI news
{{"action": "search_google", "target": "AI news"}}

User: Jarvis search YouTube for Python tutorials
{{"action": "search_youtube", "target": "Python tutorials"}}

User: Jarvis trending videos in YouTube
{{"action": "search_youtube", "target": "trending videos"}}

User: Jarvis search YouTube for trending videos
{{"action": "search_youtube", "target": "trending videos"}}

User: Jarvis what is my battery
{{"action": "battery_status", "target": "battery"}}

User: Jarvis what time is it
{{"action": "current_time", "target": "time"}}

User: Jarvis how much storage do I have
{{"action": "disk_space", "target": "disk"}}

User: Jarvis what is my CPU usage
{{"action": "cpu_usage", "target": "cpu"}}

User: Jarvis lock my Mac
{{"action": "lock_mac", "target": "mac"}}

User: Jarvis open YouTube and search for trending videos
{{"action": "search_youtube", "target": "trending videos"}}

User: Jarvis open Google and search for dopamine transporter papers
{{"action": "search_google", "target": "dopamine transporter papers"}}

User: Jarvis take a screenshot
{{"action": "take_screenshot", "target": "screen"}}

User: Jarvis screenshot my screen
{{"action": "take_and_open_screenshot", "target": "screen"}}

User: Jarvis what is on my screen
{{"action": "analyze_screen", "target": "screen"}}

User: Jarvis read this error
{{"action": "analyze_screen", "target": "screen"}}

User: Jarvis analyze my screen
{{"action": "analyze_screen", "target": "screen"}}

User: Jarvis look at my screen
{{"action": "analyze_screen_vision", "target": "screen"}}

User: Jarvis visually analyze my screen
{{"action": "analyze_screen_vision", "target": "screen"}}

User: Jarvis what do you see on my screen
{{"action": "analyze_screen_vision", "target": "screen"}}

User: Jarvis find me LangGraph tutorials
{{"action": "planner", "target": "find me LangGraph tutorials"}}

User: Jarvis research dopamine transporter papers
{{"action": "planner", "target": "research dopamine transporter papers"}}

User: Jarvis plan how to learn Python
{{"action": "planner", "target": "plan how to learn Python"}}

User: Jarvis open my AI setup
{{"action": "run_profile", "target": "ai"}}

User: Jarvis my AI setup
{{"action": "run_profile", "target": "ai"}}

User: Jarvis open my coding setup
{{"action": "run_profile", "target": "coding"}}

User: Jarvis open my research setup
{{"action": "run_profile", "target": "research"}}

User: Jarvis open Jarvis project
{{"action": "open_project", "target": "jarvis"}}

User: Jarvis open my Jarvis workspace
{{"action": "open_project", "target": "jarvis"}}

Now parse this command:

User: {user_text}
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

    content = response["message"]["content"].strip()

    print("RAW OLLAMA RESPONSE:", content)

    try:
        return extract_json(content)
    
    except Exception:
        return {
            "action": "unknown",
            "target": user_text
        }