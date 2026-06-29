from core.executor import execute_command
from core.memory_store import get_last_command, load_memory, save_memory
from core.memory_profiles import get_profile, load_profiles


class MemoryAgent:
    name = "memory"

    def run(self, task: str, speak) -> None:
        execute_command(task, speak)

    def get_last_command(self) -> dict:
        return get_last_command()

    def load_memory(self) -> dict:
        return load_memory()

    def save_memory(self, action: str, target: str) -> None:
        save_memory(action, target)

    def get_profile(self, name: str):
        return get_profile(name)

    def load_profiles(self):
        return load_profiles()
