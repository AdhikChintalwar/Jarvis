from brain.router import choose_agent
from agents.desktop_agent import decide_desktop_action
from agents.browser_agent import decide_browser_action


def coordinate_task(task: str) -> dict:
    agent = choose_agent(task)

    print("Selected agent:", agent)

    if agent == "desktop":
        decision = decide_desktop_action(task)

    elif agent == "browser":
        decision = decide_browser_action(task)

    else:
        decision = {
            "tool": "planner",
            "target": task
        }

    print("Coordinator decision:", decision)

    return decision