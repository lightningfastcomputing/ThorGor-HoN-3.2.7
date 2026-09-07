import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

from thorgor.tools.remote_client import launch


class RemoteClientInstanceTests(unittest.TestCase):
    def test_three_instances_share_one_connectivity_check_and_launch_command(self):
        processes = [SimpleNamespace(pid=100 + index) for index in range(3)]
        with (
            patch("thorgor.tools.remote_client.chat_reachable", return_value=True) as reachable,
            patch("thorgor.tools.remote_client.player_command", return_value=["hon.exe"]) as command,
            patch("thorgor.tools.remote_client.server_is_local", return_value=False),
            patch("thorgor.tools.remote_client.subprocess.Popen", side_effect=processes) as popen,
        ):
            self.assertEqual(launch(Path("C:/HoN"), "192.168.1.20", 3), 0)
        reachable.assert_called_once_with("192.168.1.20")
        command.assert_called_once_with(Path("C:/HoN"), "192.168.1.20")
        self.assertEqual(popen.call_args_list, [call(["hon.exe"], cwd=Path("C:/HoN"))] * 3)

    def test_instance_count_is_bounded_before_network_or_process_work(self):
        for invalid in (0, 11):
            with patch("thorgor.tools.remote_client.chat_reachable") as reachable:
                with self.assertRaises(ValueError):
                    launch(Path("C:/HoN"), "127.0.0.1", invalid)
                reachable.assert_not_called()


if __name__ == "__main__":
    unittest.main()
