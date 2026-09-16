from __future__ import annotations

from datetime import datetime

from core.event_bus import publish
from core.notification_service import send_notification


def test_notification_job() -> None:
    """
    Temporary job used to verify that background scheduling works.
    """
    current_time = datetime.now().strftime("%I:%M:%S %p")

    publish(
        "scheduled_job_started",
        {
            "job_type": "test_notification",
            "started_at": current_time,
        },
    )

    send_notification(
        title="Baby Background Test",
        message=f"The scheduler ran successfully at {current_time}.",
        subtitle="Scheduled task",
    )

    publish(
        "scheduled_job_finished",
        {
            "job_type": "test_notification",
            "finished_at": current_time,
        },
    )


def reminder_job(
    reminder_id: str,
    message: str,
    title: str = "Baby Reminder",
) -> None:
    """
    Generic function that future reminder schedules will execute.
    """
    publish(
        "scheduled_job_started",
        {
            "job_type": "reminder",
            "reminder_id": reminder_id,
            "message": message,
        },
    )

    send_notification(
        title=title,
        message=message,
        subtitle="Reminder",
    )

    publish(
        "scheduled_job_finished",
        {
            "job_type": "reminder",
            "reminder_id": reminder_id,
        },
    )