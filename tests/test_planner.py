import unittest
from unittest.mock import patch, MagicMock

from core.planner import extract_json, create_plan


class TestExtractJson(unittest.TestCase):
    def test_parses_json_embedded_in_text(self):
        content = 'Here is the plan:\n{"plan": [{"tool": "search_google", "target": "test"}]}\nDone.'
        result = extract_json(content)
        self.assertEqual(result["plan"][0]["tool"], "search_google")
        self.assertEqual(result["plan"][0]["target"], "test")

    def test_raises_when_no_json(self):
        with self.assertRaises(ValueError):
            extract_json("no json here")


class TestCreatePlan(unittest.TestCase):
    @patch("core.planner.ollama.chat")
    def test_returns_parsed_plan(self, mock_chat):
        mock_chat.return_value = {
            "message": {
                "content": '{"plan": [{"tool": "run_profile", "target": "coding"}]}'
            }
        }
        plan = create_plan("Open my coding setup")
        self.assertEqual(plan["plan"][0]["tool"], "run_profile")
        self.assertEqual(plan["plan"][0]["target"], "coding")

    @patch("core.planner.ollama.chat")
    def test_falls_back_to_search_google_on_invalid_json(self, mock_chat):
        mock_chat.return_value = {"message": {"content": "not valid json"}}
        plan = create_plan("research dopamine papers")
        self.assertEqual(len(plan["plan"]), 1)
        self.assertEqual(plan["plan"][0]["tool"], "search_google")
        self.assertEqual(plan["plan"][0]["target"], "research dopamine papers")


if __name__ == "__main__":
    unittest.main()
