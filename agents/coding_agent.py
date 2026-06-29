from core.executor import execute_command


class CodingAgent:
    name = "coding"

    def run(self, task: str, speak) -> None:
        execute_command(task, speak)
