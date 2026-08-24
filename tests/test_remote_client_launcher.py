import tempfile
import unittest
from pathlib import Path

from thorgor.tools.remote_client import (
    CHAT_HOSTNAME,
    configured_hosts_text,
    ipv4,
    player_command,
)


ROOT = Path(__file__).resolve().parents[1]


class RemoteClientLauncherTests(unittest.TestCase):
    def test_starter_is_adjacent_to_stack_launcher_and_uses_package_commands(self):
        stack = ROOT / "thorgor" / "START_STACK.bat"
        remote = ROOT / "thorgor" / "START_REMOTE_CLIENT.bat"
        self.assertTrue(stack.is_file())
        self.assertTrue(remote.is_file())
        source = remote.read_text(encoding="utf-8")
        self.assertIn("'remote-setup'", source)
        self.assertIn("-m thorgor remote-client", source)
        self.assertIn(r"C:\intelprop\Heroes of Newerth", source)
        self.assertNotIn("INSTALL_V77_PATCHES.ps1", source)
        self.assertNotIn("SET_CHAT_HOST.ps1", source)

    def test_hosts_rewrite_replaces_only_prior_chat_mapping(self):
        source = (
            "# sample\n"
            "127.0.0.1 localhost\n"
            f"10.0.0.2 {CHAT_HOSTNAME} # old\n"
            "10.0.0.3 unrelated.example\n"
        )
        result = configured_hosts_text(source, "192.168.1.50")
        self.assertNotIn(f"10.0.0.2 {CHAT_HOSTNAME}", result)
        self.assertIn("127.0.0.1 localhost", result)
        self.assertIn("10.0.0.3 unrelated.example", result)
        self.assertEqual(result.count(CHAT_HOSTNAME), 1)
        self.assertIn(f"192.168.1.50 {CHAT_HOSTNAME}", result)

    def test_ipv4_validation_and_player_command(self):
        self.assertEqual(ipv4("192.168.1.50"), "192.168.1.50")
        with self.assertRaises(ValueError):
            ipv4("::1")
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "hon.exe").touch()
            self.assertEqual(
                player_command(home, "192.168.1.50"),
                [str(home / "hon.exe"), "-masterserver", "192.168.1.50"],
            )


if __name__ == "__main__":
    unittest.main()
