import unittest
from pathlib import Path
from unittest.mock import patch

from thorgor.game_manager.manager_process import manager_command
from thorgor.game_manager.performance import client_affinity_mask, resolve_dedicated_cpu
from thorgor.game_manager.stack import build_stack


class PerformanceIsolationTests(unittest.TestCase):
    def test_auto_reserves_last_logical_cpu_on_normal_game_pc(self):
        self.assertEqual(resolve_dedicated_cpu("auto", 16), 15)
        self.assertEqual(resolve_dedicated_cpu("auto", 4), 3)
        self.assertIsNone(resolve_dedicated_cpu("auto", 2))

    def test_override_and_opt_out(self):
        self.assertEqual(resolve_dedicated_cpu("3", 8), 3)
        for value in ("off", "none", "all", "-1"):
            self.assertIsNone(resolve_dedicated_cpu(value, 8))
        with self.assertRaises(ValueError):
            resolve_dedicated_cpu("8", 8)

    def test_client_mask_excludes_reserved_cpu_and_smt_sibling(self):
        self.assertEqual(client_affinity_mask(3, 8), 0b11110011)
        self.assertEqual(client_affinity_mask(6, 8), 0b00111111)
        self.assertIsNone(client_affinity_mask(None, 8))

    def test_manager_command_uses_selected_cpu_not_cpu_zero(self):
        with patch.object(Path, "is_file", return_value=True):
            command = manager_command(Path("C:/HoN"), 7)
        settings = command[command.index("-execute") + 1]
        self.assertIn("Set man_allowCPUs 7", settings)
        self.assertNotIn("Set man_allowCPUs 0", settings)

    def test_normal_stack_does_not_enable_long_route_capture(self):
        services = build_stack(
            lan_ip="192.168.1.10",
            hon_home=Path("C:/HoN"),
            package_parent=Path("C:/ThorGor"),
            data_root=Path("C:/ThorGor/var"),
        )
        udp = next(service for service in services if service.name == "udp")
        self.assertNotIn("--route-trace-seconds", udp.arguments)


if __name__ == "__main__":
    unittest.main()
