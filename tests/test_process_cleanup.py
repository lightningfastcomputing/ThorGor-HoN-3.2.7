import subprocess
import unittest
from unittest.mock import patch

from thorgor.game_manager.process_cleanup import (
    cleanup_stale_processes,
    discover_listener_processes,
)


class ProcessCleanupTests(unittest.TestCase):
    @patch("thorgor.game_manager.process_cleanup.os.name", "nt")
    @patch("thorgor.game_manager.process_cleanup.subprocess.run")
    def test_discovers_stack_listener_when_command_line_is_hidden(self, run):
        run.side_effect = (
            subprocess.CompletedProcess([], 0, "TCP    0.0.0.0:11031  0.0.0.0:0  LISTENING  55\n", ""),
            subprocess.CompletedProcess([], 0, "UDP    0.0.0.0:11236  *:*  77\n", ""),
        )

        self.assertEqual(
            discover_listener_processes(),
            ((55, "listener", "TCP 0.0.0.0:11031"), (77, "listener", "UDP 0.0.0.0:11236")),
        )

    @patch("thorgor.game_manager.process_cleanup.os.getpid", return_value=900)
    @patch("thorgor.game_manager.process_cleanup.discover_listener_processes", return_value=())
    @patch("thorgor.game_manager.process_cleanup.discover_processes")
    @patch("thorgor.game_manager.process_cleanup.subprocess.run")
    def test_reports_only_successfully_stopped_processes(self, run, discover, _listeners, _getpid):
        discover.return_value = ((101, "python.exe", "-m thorgor.protocols.game_protocol"),)
        run.return_value = subprocess.CompletedProcess([], 0, "SUCCESS", "")

        self.assertEqual(cleanup_stale_processes(), (101,))

    @patch("thorgor.game_manager.process_cleanup.os.getpid", return_value=900)
    @patch("thorgor.game_manager.process_cleanup.discover_listener_processes", return_value=())
    @patch("thorgor.game_manager.process_cleanup.discover_processes")
    @patch("thorgor.game_manager.process_cleanup.subprocess.run")
    def test_fails_startup_when_stale_process_cannot_be_stopped(self, run, discover, _listeners, _getpid):
        discover.return_value = ((101, "python.exe", "-m thorgor.protocols.game_protocol"),)
        run.return_value = subprocess.CompletedProcess([], 5, "", "Access is denied")

        with self.assertRaisesRegex(RuntimeError, "Access is denied"):
            cleanup_stale_processes()


if __name__ == "__main__":
    unittest.main()
