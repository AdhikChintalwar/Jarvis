import psutil
import shutil
import datetime
import subprocess


def get_battery_status() -> str:
    battery = psutil.sensors_battery()

    if battery is None:
        return "Battery information is not available."

    percent = battery.percent
    plugged = battery.power_plugged

    status = "charging" if plugged else "not charging"

    return f"Battery is at {percent}% and is {status}."


def get_current_time() -> str:
    now = datetime.datetime.now()
    return now.strftime("It is %I:%M %p.")


def get_disk_space() -> str:
    total, used, free = shutil.disk_usage("/")

    free_gb = round(free / (1024 ** 3), 2)
    total_gb = round(total / (1024 ** 3), 2)

    return f"You have {free_gb} GB free out of {total_gb} GB."


def get_cpu_usage() -> str:
    cpu = psutil.cpu_percent(interval=1)
    return f"CPU usage is {cpu}%."


def lock_mac() -> str:
    subprocess.run([
        "pmset",
        "displaysleepnow"
    ])

    return "Locked the screen."