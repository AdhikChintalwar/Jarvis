from brain.router import choose_agent
from agents.desktop_agent import decide_desktop_action
from agents.browser_agent import decide_browser_action
from core.portal_state import write_state
from core.event_bus import publish

def reset_agents():
    return {
        "desktop": "idle",
        "browser": "idle",
        "coding": "idle",
        "memory": "idle",
        "planner": "idle",
    }


def coordinate_task(task: str) -> dict:
    """
    Routes a task to the correct agent and returns a tool decision.

    Returns:
    {
        "tool": "...",
        "target": "..."
    }
    """

    # -----------------------------
    # Step 1 : Router
    # -----------------------------
    agent = choose_agent(task)
    publish("agent_selected", {"agent": agent})
    print(f"Selected agent: {agent}")

    agents = reset_agents()
    agents[agent] = "working"

    write_state(
        status="routing",
        active_agent=agent,
        baby_text=f"Routing task to {agent.capitalize()} Agent...",
        agents=agents
    )

    # -----------------------------
    # Step 2 : Agent reasoning
    # -----------------------------
    if agent == "desktop":
        decision = decide_desktop_action(task)

    elif agent == "browser":
        decision = decide_browser_action(task)

    elif agent == "coding":
        # Coding Agent not built yet
        decision = {
            "tool": "planner",
            "target": task
        }

    elif agent == "memory":
        # Memory Agent not built yet
        decision = {
            "tool": "planner",
            "target": task
        }

    else:
        decision = {
            "tool": "planner",
            "target": task
        }

    print("Coordinator decision:", decision)

    # -----------------------------
    # Step 3 : Update Portal
    # -----------------------------
    agents = reset_agents()
    agents[agent] = "done"

    write_state(
        status="executing",
        active_agent=agent,
        baby_text=f"{agent.capitalize()} Agent selected '{decision['tool']}'",
        agents=agents
    )

    return decision