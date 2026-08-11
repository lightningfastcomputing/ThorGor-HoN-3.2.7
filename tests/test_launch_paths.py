import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_HON_HOME = r"C:\Program Files (x86)\Heroes of Newerth"


class LaunchPathTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_hon_launchers_use_canonical_program_files_home(self):
        launchers = (
            "1_START_V61_COMPLETE_REGISTRY_GUARD.bat",
            "START_LOCAL_PLAYER.bat",
            "remote-client/START_REMOTE_PLAYER.bat",
            "start_manager_v39.ps1",
            "hon_v49_dashboard.py",
        )
        for relative in launchers:
            text = self.read(relative)
            self.assertIn(CANONICAL_HON_HOME, text, relative)

    def test_manager_runs_from_hon_home(self):
        manager = self.read("start_manager_v39.ps1")
        dashboard = self.read("hon_v49_dashboard.py")
        self.assertIn("Set-Location -LiteralPath $HonHome", manager)
        self.assertIn('"-HonHome", str(HON_HOME)', dashboard)
        self.assertIn("], HON_HOME)", dashboard)

    def test_default_patch_paths_do_not_prefer_development_install(self):
        for relative in ("PATCH_K2_V57.ps1", "PATCH_CGAME_V61.ps1"):
            text = self.read(relative)
            self.assertIn(CANONICAL_HON_HOME, text, relative)

    def test_runtime_uses_validated_python_and_host_safe_player_guard(self):
        server = self.read("1_START_V61_COMPLETE_REGISTRY_GUARD.bat")
        remote = self.read("remote-client/START_REMOTE_PLAYER.bat")
        dashboard = self.read("hon_v49_dashboard.py")
        self.assertIn("FIND_PYTHON.ps1", server)
        self.assertIn("CHECK_HON_PLAYER_NOT_RUNNING.ps1", remote)
        self.assertIn("PYTHON = sys.executable", dashboard)


if __name__ == "__main__":
    unittest.main()
