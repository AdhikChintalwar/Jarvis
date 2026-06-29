from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path


_subscribers = defaultdict(list)

EVENT_LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "events.jsonl"


def subscribe(event_name: str, handler):
    _subscribers[event_name].append(handler)


def publish(event_name: str, data: dict | None = None):
    event = {
        "type": event_name,
        "data": data or {},
        "timestamp": datetime.now().isoformat()
    }

    print(f"EVENT: {event_name} -> {event['data']}")

    EVENT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(EVENT_LOG_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")

    for handler in _subscribers.get(event_name, []):
        try:
            handler(event)
        except Exception as e:
            print(f"Event handler error for {event_name}: {e}")

    for handler in _subscribers.get("*", []):
        try:
            handler(event)
        except Exception as e:
            print(f"Wildcard event handler error: {e}")