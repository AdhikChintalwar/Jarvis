from __future__ import annotations

import atexit
import threading
from datetime import datetime
from typing import Any

from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MISSED,
    JobExecutionEvent,
)
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.event_bus import publish
from core.scheduled_jobs import reminder_job, test_notification_job


_scheduler: BackgroundScheduler | None = None
_scheduler_lock = threading.Lock()


def _handle_job_event(event: JobExecutionEvent) -> None:
    """
    Publish scheduler results to Baby's event system.
    """
    if event.exception:
        print(
            f"Scheduled job failed: {event.job_id}: "
            f"{event.exception}"
        )

        publish(
            "scheduler_job_error",
            {
                "job_id": event.job_id,
                "error": str(event.exception),
            },
        )

    elif event.code == EVENT_JOB_MISSED:
        print(f"Scheduled job was missed: {event.job_id}")

        publish(
            "scheduler_job_missed",
            {
                "job_id": event.job_id,
            },
        )

    else:
        print(f"Scheduled job completed: {event.job_id}")

        publish(
            "scheduler_job_executed",
            {
                "job_id": event.job_id,
            },
        )


def get_scheduler() -> BackgroundScheduler:
    global _scheduler

    if _scheduler is None:
        raise RuntimeError(
            "The scheduler has not been started. "
            "Call start_scheduler() first."
        )

    return _scheduler


def start_scheduler() -> BackgroundScheduler:
    """
    Start Baby's scheduler once in a background thread.
    """
    global _scheduler

    with _scheduler_lock:
        if _scheduler is not None and _scheduler.running:
            return _scheduler

        _scheduler = BackgroundScheduler(
            timezone="local",
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 60,
            },
        )

        _scheduler.add_listener(
            _handle_job_event,
            EVENT_JOB_EXECUTED
            | EVENT_JOB_ERROR
            | EVENT_JOB_MISSED,
        )

        _scheduler.start()

        publish(
            "scheduler_started",
            {
                "running": True,
            },
        )

        print("Baby background scheduler started.")

        return _scheduler


def stop_scheduler(wait: bool = False) -> None:
    global _scheduler

    with _scheduler_lock:
        if _scheduler is None:
            return

        if _scheduler.running:
            _scheduler.shutdown(wait=wait)

        _scheduler = None

        publish(
            "scheduler_stopped",
            {
                "running": False,
            },
        )

        print("Baby background scheduler stopped.")
def schedule_test_notification(
    seconds: int = 20,
) -> str:
    """
    Schedule one test notification after a short delay.
    """
    from datetime import timedelta

    if seconds < 1:
        raise ValueError("seconds must be at least 1")

    scheduler = get_scheduler()
    run_at = datetime.now().astimezone() + timedelta(seconds=seconds)

    job = scheduler.add_job(
        test_notification_job,
        trigger=DateTrigger(
            run_date=run_at,
            timezone=run_at.tzinfo,
        ),
        id="baby_test_notification",
        replace_existing=True,
    )

    publish(
        "scheduled_job_created",
        {
            "job_id": job.id,
            "job_type": "test_notification",
            "run_at": run_at.isoformat(),
        },
    )

    print(
        f"Test notification scheduled for "
        f"{run_at.strftime('%I:%M:%S %p')}."
    )

    return job.id

def schedule_interval_reminder(
    reminder_id: str,
    message: str,
    minutes: int,
    title: str = "Baby Reminder",
) -> str:
    """
    Schedule a recurring reminder at a fixed minute interval.
    """
    if not reminder_id.strip():
        raise ValueError("reminder_id cannot be empty")

    if not message.strip():
        raise ValueError("message cannot be empty")

    if minutes < 1:
        raise ValueError("minutes must be at least 1")

    scheduler = get_scheduler()

    job = scheduler.add_job(
        reminder_job,
        trigger=IntervalTrigger(minutes=minutes),
        id=reminder_id,
        replace_existing=True,
        kwargs={
            "reminder_id": reminder_id,
            "message": message,
            "title": title,
        },
    )

    publish(
        "scheduled_job_created",
        {
            "job_id": job.id,
            "job_type": "interval_reminder",
            "message": message,
            "minutes": minutes,
        },
    )

    return job.id


def remove_scheduled_job(job_id: str) -> bool:
    scheduler = get_scheduler()

    try:
        scheduler.remove_job(job_id)

        publish(
            "scheduled_job_removed",
            {
                "job_id": job_id,
            },
        )

        return True

    except JobLookupError:
        return False


def list_scheduled_jobs() -> list[dict[str, Any]]:
    scheduler = get_scheduler()
    jobs = []

    for job in scheduler.get_jobs():
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": (
                    job.next_run_time.isoformat()
                    if job.next_run_time
                    else None
                ),
                "trigger": str(job.trigger),
            }
        )

    return jobs


atexit.register(stop_scheduler)