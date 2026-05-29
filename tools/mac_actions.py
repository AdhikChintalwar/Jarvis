import json
import subprocess
from pathlib import Path
import time
CONFIG_PATH = Path(__file__).parent / "config.json"

with open(CONFIG_PATH, "r") as f:
    CONFIG = json.load(f)


def open_app(app_key: str) -> str:
    app_key = app_key.lower().strip()
    app_name = CONFIG["apps"].get(app_key, app_key)

    subprocess.run(["open", "-a", app_name])
    return f"Opened app: {app_name}"


def open_website(site_key: str) -> str:
    site_key = site_key.lower().strip()
    url = CONFIG["websites"].get(site_key, site_key)

    if not url.startswith("http"):
        url = "https://" + url

    subprocess.run(["open", url])
    return f"Opened website: {url}"


def open_folder(path: str) -> str:
    path = path.strip().replace("~", str(Path.home()))
    subprocess.run(["open", path])
    return f"Opened folder: {path}"

def run_profile(profile_name: str) -> str:
    profile_name = profile_name.lower().strip()

    profiles = CONFIG.get("profiles", {})

    if profile_name not in profiles:
        return f"Profile '{profile_name}' not found"

    apps = profiles[profile_name]

    for app in apps:
        subprocess.run(["open", "-a", app])
        time.sleep(1)

    return f"Started profile: {profile_name}"