import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "thorgor" / "runtime"


class MigrationInventoryTests(unittest.TestCase):
    """Freeze the compatibility payload so migrations are explicit."""

    def test_live_python_entrypoint_inventory_is_complete(self):
        expected = {
            "thorgor_hon_sandboxed_masterserver_v39.py",
            "chat-server/thorgor_hon_chatserver_v13.py",
            "hon_udp_shim.py",
            "hon_manager_status_bridge_v42.py",
            "hon_native_matchid_bridge_v47.py",
            "hon_v49_dashboard.py",
            "manage_accounts_v43.py",
        }
        actual = {
            path.relative_to(RUNTIME).as_posix()
            for path in RUNTIME.rglob("*.py")
            if "patches" not in path.parts
        }
        self.assertEqual(actual, expected)

    def test_live_process_orchestration_inventory_is_complete(self):
        expected = {
            "start_manager_v39.ps1",
            "RESET_V42.ps1",
            "CLEANUP_OLD_TESTS.ps1",
            "CHECK_RUNTIME.ps1",
            "2_CHECK_V45.bat",
        }
        actual = {
            path.name
            for path in RUNTIME.iterdir()
            if path.suffix.lower() in {".ps1", ".bat"}
            and not path.name.startswith(("PATCH_", "INSTALL_", "FIND_"))
        }
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
