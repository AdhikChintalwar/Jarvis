from core.event_bus import subscribe
from core.portal_state import write_state


def portal_event_handler(event):
    event_type = event["type"]
    data = event["data"]

    if event_type == "session_started":
        write_state(
            status="listening",
            baby_text="Listening...",
            active_agent="none"
        )

    elif event_type == "speech_recognized":
        write_state(
            status="processing",
            user_text=data.get("text", ""),
            baby_text="Understanding command..."
        )

    elif event_type == "tasks_split":
        write_state(
            status="routing",
            baby_text=f"Split into {len(data.get('tasks', []))} task(s)"
        )

    elif event_type == "agent_selected":
        agent = data.get("agent", "none")
        write_state(
            status="routing",
            active_agent=agent,
            baby_text=f"Routing to {agent} agent",
            agents={agent: "working"}
        )

    elif event_type == "tool_started":
        write_state(
            status="executing",
            baby_text=f"Executing {data.get('tool', '')}"
        )

    elif event_type == "tool_finished":
        write_state(
            status="listening",
            baby_text="Ready for next command",
            active_agent="none"
        )

    elif event_type == "session_ended":
        write_state(
            status="idle",
            baby_text="Waiting for wake word...",
            active_agent="none"
        )


def register_event_handlers():
    subscribe("*", portal_event_handler)