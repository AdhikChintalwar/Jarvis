from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_ROOT / "data" / "workspace_context.json"


DEFAULT_CONTEXT = {
    "current_project": "Baby",
    "project_path": str(PROJECT_ROOT),
    "git_branch": None,
    "recent_files": [],
    "important_files": [
        "jarvis_main.py",
        "core/executor.py",
        "core/session_manager.py",
        "brain/router.py",
        "brain/coordinator.py",
        "agents/coding_agent.py",
    ],
}


def _run_git_command(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip() or None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def get_git_branch() -> str | None:
    return _run_git_command("branch", "--show-current")


def get_recent_files(limit: int = 10) -> list[str]:
    ignored_parts = {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        "models",
        "dist",
        "build",
    }

    files: list[Path] = []

    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue

        if any(part in ignored_parts for part in path.parts):
            continue

        try:
            path.stat()
            files.append(path)
        except OSError:
            continue

    files.sort(
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    return [
        str(path.relative_to(PROJECT_ROOT))
        for path in files[:limit]
    ]


def build_workspace_context() -> dict[str, Any]:
    return {
        **DEFAULT_CONTEXT,
        "git_branch": get_git_branch(),
        "recent_files": get_recent_files(),
    }


def save_workspace_context(context: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(context, indent=2),
        encoding="utf-8",
    )


def load_workspace_context() -> dict[str, Any]:
    if not STATE_FILE.exists():
        context = build_workspace_context()
        save_workspace_context(context)
        return context

    try:
        stored = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        stored = {}

    current = build_workspace_context()
    current.update(stored)

    current["git_branch"] = get_git_branch()
    current["recent_files"] = get_recent_files()

    return current


def refresh_workspace_context() -> dict[str, Any]:
    context = build_workspace_context()
    save_workspace_context(context)
    return context


def set_current_project(name: str, path: str) -> dict[str, Any]:
    project_path = Path(path).expanduser().resolve()

    context = load_workspace_context()
    context["current_project"] = name
    context["project_path"] = str(project_path)

    save_workspace_context(context)
    return context


def describe_workspace() -> str:
    context = load_workspace_context()

    recent = context.get("recent_files", [])
    recent_text = ", ".join(recent[:5]) if recent else "No recent files"

    return (
        f"Current project: {context.get('current_project', 'Unknown')}. "
        f"Project path: {context.get('project_path', 'Unknown')}. "
        f"Git branch: {context.get('git_branch') or 'Not available'}. "
        f"Recent files: {recent_text}."
    )