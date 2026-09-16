from __future__ import annotations

import subprocess

from core.event_bus import publish


def _escape_applescript(value: str) -> str:
    """
    Escape text before inserting it into an AppleScript string.
    """
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
    )


def send_notification(
    message: str,
    title: str = "Baby",
    subtitle: str | None = None,
) -> bool:
    """
    Display a native macOS notification.

    Returns True when the notification command succeeds.
    """
    safe_message = _escape_applescript(message)
    safe_title = _escape_applescript(title)

    script = (
        f'display notification "{safe_message}" '
        f'with title "{safe_title}"'
    )

    if subtitle:
        safe_subtitle = _escape_applescript(subtitle)
        script += f' subtitle "{safe_subtitle}"'

    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )

        publish(
            "notification_sent",
            {
                "title": title,
                "message": message,
                "subtitle": subtitle,
            },
        )

        print(f"Notification sent: {title} — {message}")
        return True

    except subprocess.TimeoutExpired:
        print("Notification failed: osascript timed out.")

    except subprocess.CalledProcessError as error:
        details = error.stderr.strip() if error.stderr else str(error)
        print(f"Notification failed: {details}")

    except FileNotFoundError:
        print("Notification failed: osascript is unavailable.")

    except Exception as error:
        print(f"Unexpected notification error: {error}")

    publish(
        "notification_failed",
        {
            "title": title,
            "message": message,
        },
    )

    return False