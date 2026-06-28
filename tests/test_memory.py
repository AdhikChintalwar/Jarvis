import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import memory_store


class TestMemoryStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory_file = Path(self.temp_dir.name) / "jarvis_memory.json"
        self.patch_file = patch.object(memory_store, "MEMORY_FILE", self.memory_file)
        self.patch_file.start()

    def tearDown(self):
        self.patch_file.stop()
        self.temp_dir.cleanup()

    def test_load_memory_returns_defaults_when_missing(self):
        memory = memory_store.load_memory()
        self.assertIsNone(memory["last_action"])
        self.assertIsNone(memory["last_target"])

    def test_save_and_load_memory(self):
        memory_store.save_memory("open_app", "Safari")
        memory = memory_store.load_memory()
        self.assertEqual(memory["last_action"], "open_app")
        self.assertEqual(memory["last_target"], "Safari")

    def test_get_last_command(self):
        memory_store.save_memory("open_website", "github.com")
        last = memory_store.get_last_command()
        self.assertEqual(last["last_action"], "open_website")
        self.assertEqual(last["last_target"], "github.com")

    def test_overwrites_previous_memory(self):
        memory_store.save_memory("open_app", "Notes")
        memory_store.save_memory("run_profile", "coding")
        memory = memory_store.load_memory()
        self.assertEqual(memory["last_action"], "run_profile")
        self.assertEqual(memory["last_target"], "coding")

    def test_load_memory_reads_existing_file(self):
        self.memory_file.write_text(
            json.dumps({"last_action": "lock_mac", "last_target": ""}),
            encoding="utf-8",
        )
        memory = memory_store.load_memory()
        self.assertEqual(memory["last_action"], "lock_mac")


if __name__ == "__main__":
    unittest.main()
