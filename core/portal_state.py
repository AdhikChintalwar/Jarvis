import json
from pathlib import Path
from datetime import datetime


STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "portal_state.json"


DEFAULT_STATE = {
    "status": "idle",
    "user_text": "",
    "baby_text": "Waiting for wake word...",
    "active_agent": "none",
    "agents": {
        "desktop": "idle",
        "browser": "idle",
        "coding": "idle",
        "memory": "idle",
        "planner": "idle"
    },
    "updated_at": ""
}


def write_state(**updates):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    state = DEFAULT_STATE.copy()
    state["agents"] = DEFAULT_STATE["agents"].copy()

    if STATE_FILE.exists():
        try:
            existing = json.loads(STATE_FILE.read_text())
            state.update(existing)
            state["agents"].update(existing.get("agents", {}))
        except Exception:
            pass

    for key, value in updates.items():
        if key == "agents":
            state["agents"].update(value)
        else:
            state[key] = value

    state["updated_at"] = datetime.now().isoformat()

    STATE_FILE.write_text(json.dumps(state, indent=2))