from core.workspace_context import (
    describe_workspace,
    load_workspace_context,
    refresh_workspace_context,
)


def handle_workspace_task(task: str) -> dict:
    text = task.lower().strip()

    if any(
        phrase in text
        for phrase in [
            "what project am i working on",
            "current project",
            "workspace status",
            "what workspace",
        ]
    ):
        return {
            "tool": "workspace_answer",
            "target": describe_workspace(),
        }

    if any(
        phrase in text
        for phrase in [
            "refresh workspace",
            "refresh project context",
            "scan workspace",
        ]
    ):
        context = refresh_workspace_context()

        return {
            "tool": "workspace_answer",
            "target": (
                f"Workspace refreshed. Current project is "
                f"{context.get('current_project', 'Unknown')} on branch "
                f"{context.get('git_branch') or 'unknown'}."
            ),
        }

    if any(
        phrase in text
        for phrase in [
            "recent files",
            "recently changed files",
            "what files changed",
        ]
    ):
        context = load_workspace_context()
        files = context.get("recent_files", [])

        if not files:
            answer = "I could not find any recent project files."
        else:
            answer = "Recent files are: " + ", ".join(files[:8])

        return {
            "tool": "workspace_answer",
            "target": answer,
        }

    return {
        "tool": "workspace_answer",
        "target": describe_workspace(),
    }