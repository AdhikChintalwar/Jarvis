from core.executor import execute_command
from core.planner import create_plan


class PlannerAgent:
    name = "planner"

    def run(self, task: str, speak) -> None:
        execute_command(task, speak)

    def create_plan(self, goal: str) -> dict:
        return create_plan(goal)
