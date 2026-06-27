import json
from pathlib import Path

MEMORY_FILE = Path(__file__).parent / "user_memory.json"


def load_profiles():

    with open(MEMORY_FILE, "r") as f:
        return json.load(f)


def get_profile(name):

    profiles = load_profiles()

    return profiles.get(name.lower())