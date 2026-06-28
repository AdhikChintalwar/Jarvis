import unittest
from unittest.mock import patch, MagicMock

from core.executor import VALID_ACTIONS, execute_command


class TestValidActions(unittest.TestCase):
    def test_planner_action_is_valid(self):
        self.assertIn("planner", VALID_ACTIONS)

    def test_core_skills_are_valid(self):
        expected = {
            "open_app", "search_google", "search_youtube",
            "battery_status", "take_screenshot", "run_profile",
        }
        self.assertTrue(expected.issubset(VALID_ACTIONS))


class TestExecuteCommand(unittest.TestCase):
    @patch("core.executor.understand_command")
    def test_ignores_unknown_action(self, mock_understand):
        mock_understand.return_value = {"action": "invalid_action", "target": "x"}
        speak = MagicMock()
        execute_command("do something weird", speak)
        speak.assert_not_called()

    @patch("core.executor.run_mcp")
    @patch("core.executor.understand_command")
    def test_routes_open_app(self, mock_understand, mock_run_mcp):
        mock_understand.return_value = {"action": "open_app", "target": "Safari"}
        mock_run_mcp.return_value = MagicMock()
        speak = MagicMock()

        with patch("core.executor.save_memory"):
            execute_command("open Safari", speak)

        speak.assert_called_with("Opening Safari")
        mock_run_mcp.assert_called_once_with("jarvis_open_app", {"app_name": "Safari"})

    @patch("core.executor.create_plan")
    @patch("core.executor.understand_command")
    def test_routes_research_to_planner(self, mock_understand, mock_create_plan):
        mock_understand.return_value = {"action": "unknown", "target": ""}
        mock_create_plan.return_value = {"plan": []}
        speak = MagicMock()

        execute_command("find good Python tutorials", speak)

        mock_create_plan.assert_called_once()
        speak.assert_any_call("Creating a plan")


if __name__ == "__main__":
    unittest.main()
