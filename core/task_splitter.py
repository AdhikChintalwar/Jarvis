from __future__ import annotations

import re


MULTI_TASK_PATTERNS = [
    r"\band then\b",
    r"\bthen\b",
    r"\bafter that\b",
    r"\bnext\b",
    r"\balso\b",
    r";",
]


def _clean_task(text: str) -> str:
    text = text.strip()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip(
        " ,;"
    )


def _looks_like_real_task(
    text: str,
) -> bool:
    text = _clean_task(text)

    if not text:
        return False

    words = text.split()

    return len(words) >= 2


def split_tasks(
    command_text: str,
) -> list[str]:
    """
    Fast local task splitter.

    Most voice commands are a single task, so they return immediately
    without calling an LLM.

    Examples:

        "What's the time?"
        ->
        ["What's the time?"]

        "Open Chrome and then search Google for Python"
        ->
        [
            "Open Chrome",
            "search Google for Python",
        ]
    """

    if not isinstance(
        command_text,
        str,
    ):
        return []

    text = command_text.strip()

    if not text:
        return []

    # ---------------------------------------------------------
    # First determine whether this even looks multi-step.
    # ---------------------------------------------------------

    lowered = text.lower()

    has_separator = any(
        re.search(
            pattern,
            lowered,
            flags=re.IGNORECASE,
        )
        for pattern in MULTI_TASK_PATTERNS
    )

    if not has_separator:
        return [text]

    # ---------------------------------------------------------
    # Split only on explicit sequential connectors.
    # Do NOT split every normal "and".
    # ---------------------------------------------------------

    split_pattern = (
        r"\s+(?:and then|after that|then|also|next)\s+"
        r"|;"
    )

    pieces = re.split(
        split_pattern,
        text,
        flags=re.IGNORECASE,
    )

    tasks = [
        _clean_task(piece)
        for piece in pieces
        if _looks_like_real_task(
            piece
        )
    ]

    if len(tasks) <= 1:
        return [text]

    print(
        "FAST TASK SPLIT:",
        tasks,
    )

    return tasks