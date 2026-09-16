from __future__ import annotations

import re


def normalize(
    text: str,
) -> str:
    text = text.lower().strip()

    text = re.sub(
        r"[^\w\s']+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def fast_route(
    task: str,
) -> str | None:
    """
    Fast deterministic routing.

    Obvious commands never use an LLM router.
    """

    text = normalize(task)

    if not text:
        return None

    # =========================================================
    # CURRENT SCREEN / CURRENT ACTIVITY
    # =========================================================

    screen_phrases = [
        "what am i doing",
        "what am i doing now",
        "what am i looking at",
        "what is on my screen",
        "what's on my screen",
        "what do you see",
        "what do you see now",
        "look at my screen",
        "analyze my screen",
        "analyse my screen",
        "inspect my screen",
        "look at this window",
        "what is this window",
    ]

    if any(
        phrase in text
        for phrase in screen_phrases
    ):
        print(
            "FAST ROUTER: desktop"
        )
        return "desktop"

    # =========================================================
    # WORKSPACE
    # =========================================================

    workspace_phrases = [
        "what am i working on",
        "what project am i working on",
        "which project am i working on",
        "current project",
        "current workspace",
        "workspace status",
        "project status",
        "recent files",
        "recently changed files",
        "what files changed",
        "git branch",
        "current branch",
        "project path",
    ]

    if any(
        phrase in text
        for phrase in workspace_phrases
    ):
        print(
            "FAST ROUTER: workspace"
        )
        return "workspace"

    # =========================================================
    # TIME / MAC CONTROL
    # =========================================================

    desktop_phrases = [
        "what time",
        "what's the time",
        "current time",
        "volume up",
        "volume down",
        "mute",
        "unmute",
        "brightness up",
        "brightness down",
        "mission control",
        "app switcher",
        "spotlight",
        "take screenshot",
        "take a screenshot",
        "screenshot",
    ]

    if any(
        phrase in text
        for phrase in desktop_phrases
    ):
        print(
            "FAST ROUTER: desktop"
        )
        return "desktop"

    desktop_prefixes = [
        "open ",
        "close ",
        "quit ",
        "launch ",
        "switch to ",
    ]

    if any(
        text.startswith(prefix)
        for prefix in desktop_prefixes
    ):
        print(
            "FAST ROUTER: desktop"
        )
        return "desktop"

    # =========================================================
    # BROWSER
    # =========================================================

    browser_phrases = [
        "search google",
        "google ",
        "search youtube",
        "youtube ",
        "search the web",
        "search web",
        "find online",
        "look online",
        "browse ",
        "open website",
        "go to website",
    ]

    if any(
        phrase in text
        for phrase in browser_phrases
    ):
        print(
            "FAST ROUTER: browser"
        )
        return "browser"

    # =========================================================
    # CODING
    # =========================================================

    coding_phrases = [
        "write code",
        "write python",
        "write javascript",
        "write react",
        "debug",
        "fix this code",
        "fix my code",
        "code error",
        "traceback",
        "syntax error",
        "compile",
        "refactor",
        "github",
        "git commit",
    ]

    if any(
        phrase in text
        for phrase in coding_phrases
    ):
        print(
            "FAST ROUTER: coding"
        )
        return "coding"

    # =========================================================
    # MEMORY
    # =========================================================

    memory_phrases = [
        "remember that",
        "remember this",
        "remember my",
        "what do you remember",
        "do you remember",
        "forget that",
        "forget my",
    ]

    if any(
        phrase in text
        for phrase in memory_phrases
    ):
        print(
            "FAST ROUTER: memory"
        )
        return "memory"

    # =========================================================
    # COMPLEX REQUEST
    # =========================================================

    complex_phrases = [
        "figure out",
        "investigate",
        "compare",
        "analyze why",
        "analyse why",
        "research",
        "plan how",
        "best way",
        "help me decide",
        "work together",
        "use multiple agents",
    ]

    if any(
        phrase in text
        for phrase in complex_phrases
    ):
        print(
            "FAST ROUTER: planner"
        )
        return "planner"

    return None


def route_task(
    task: str,
) -> str:
    agent = fast_route(task)

    if agent is not None:
        return agent

    print(
        "FAST ROUTER: planner fallback"
    )

    return "planner"


def route(
    task: str,
) -> str:
    return route_task(task)


def select_agent(
    task: str,
) -> str:
    return route_task(task)


def choose_agent(
    task: str,
) -> str:
    return route_task(task)