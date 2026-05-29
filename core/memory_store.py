import json
from pathlib import Path

MEMORY_FILE = Path(__file__).parent / "jarvis_memory.json"


def load_memory() -> dict:
    if not MEMORY_FILE.exists():
        return {
            "last_action": None,
            "last_target": None
        }

    with open(MEMORY_FILE, "r") as f:
        return json.load(f)


def save_memory(action: str, target: str):
    memory = {
        "last_action": action,
        "last_target": target
    }

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


def get_last_command() -> dict:
    return load_memory()