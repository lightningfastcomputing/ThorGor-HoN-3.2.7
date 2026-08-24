import tempfile
import unittest
from pathlib import Path

from thorgor.game_manager.manager_process import MANAGER_SETTINGS, manager_command
from thorgor.game_manager.process_cleanup import _is_thorgor_process


class ManagerProcessTests(unittest.TestCase):
    def test_manager_command_preserves_authentic_slave_orchestration_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "hon.exe").touch()
            command = manager_command(home)
        self.assertEqual(command[1:3], ["-manager", "-noconfig"])
        self.assertEqual(command[3], "-execute")
        self.assertEqual(command[-2:], ["-masterserver", "127.0.0.1"])
        settings = command[4].split(";")
        self.assertEqual(settings, list(MANAGER_SETTINGS))
        self.assertIn("Set man_numSlaveAccounts 1", settings)
        self.assertIn("Set man_idleTarget 1", settings)
        self.assertIn("Set man_startServerPort 11235", settings)
        self.assertIn("Set man_endServerPort 11235", settings)

    def test_dashboard_launches_stable_manager_process_module(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "thorgor" / "game_manager" / "stack.py").read_text(encoding="utf-8")
        self.assertIn('"thorgor.game_manager.manager_process"', source)
        self.assertNotIn("start_manager_v39.ps1", source)

    def test_cleanup_targets_only_stack_services_and_manager_children(self):
        self.assertTrue(_is_thorgor_process("python.exe", "python -m thorgor.master.server"))
        self.assertTrue(_is_thorgor_process("hon.exe", "hon.exe -manager -noconfig"))
        self.assertTrue(_is_thorgor_process("hon.exe", "hon.exe -dedicated -execute settings"))
        self.assertFalse(_is_thorgor_process("hon.exe", "hon.exe -mod game"))
        self.assertFalse(_is_thorgor_process("python.exe", "python -m thorgor cleanup"))


if __name__ == "__main__":
    unittest.main()
