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

    def test_player_launchers_allow_an_explicit_hon_home_override(self):
        for relative in (
            "1_START_V61_COMPLETE_REGISTRY_GUARD.bat",
            "remote-client/START_REMOTE_PLAYER.bat",
        ):
            self.assertIn(
                'if not defined HON_HOME set "HON_HOME=',
                self.read(relative),
                relative,
            )

    def test_manager_runs_from_hon_home(self):
        manager = self.read("start_manager_v39.ps1")
        dashboard = self.read("hon_v49_dashboard.py")
        self.assertIn("Set-Location -LiteralPath $HonHome", manager)
        self.assertIn('"-HonHome", str(HON_HOME)', dashboard)
        self.assertIn("], HON_HOME)", dashboard)

    def test_default_patch_paths_do_not_prefer_development_install(self):
        for relative in (
            "PATCH_K2_V57.ps1",
            "PATCH_K2_V65.ps1",
            "PATCH_CGAME_V61.ps1",
        ):
            text = self.read(relative)
            self.assertIn(CANONICAL_HON_HOME, text, relative)

    def test_server_launcher_delays_program_files_path_expansion(self):
        server = self.read("1_START_V61_COMPLETE_REGISTRY_GUARD.bat")
        self.assertIn("EnableDelayedExpansion", server)
        self.assertIn('if not exist "!HON_HOME!\\hon.exe" (', server)
        self.assertIn("echo   !HON_HOME!\\hon.exe", server)
        self.assertNotIn("echo   %HON_HOME%\\hon.exe", server)

    def test_runtime_uses_compiled_services_and_host_safe_player_guard(self):
        server = self.read("1_START_V61_COMPLETE_REGISTRY_GUARD.bat")
        remote = self.read("remote-client/START_REMOTE_PLAYER.bat")
        dashboard = self.read("hon_v49_dashboard.py")
        self.assertIn("ThorGorDashboard.exe", server)
        self.assertIn("ThorGorMasterServer.exe", server)
        self.assertIn("PATCH_K2_V65.ps1", server)
        self.assertNotIn('PATCH_K2_V57.ps1" -HonHome', server)
        self.assertNotIn("FIND_PYTHON.ps1", server)
        self.assertIn("CHECK_HON_PLAYER_NOT_RUNNING.ps1", remote)
        self.assertIn("_service_command", dashboard)
        self.assertIn("ThorGor*.exe", self.read("README.md"))

    def test_dashboard_launcher_checks_early_process_exit(self):
        launcher = self.read("START_DASHBOARD.ps1")
        self.assertIn("-RedirectStandardError $stderrLog", launcher)
        self.assertIn("if ($process.HasExited)", launcher)
        self.assertIn("dashboard-startup.stderr.log", launcher)

    def test_v75_launcher_installs_server_side_fix_without_proxy_injection(self):
        launcher = self.read("START_V75_SERVER_HERO_STATE_FIX.bat")
        dashboard = self.read("hon_v49_dashboard.py")
        self.assertIn("INSTALL_V75_PATCHES.ps1", launcher)
        self.assertIn("PATCH_K2_V75.ps1", self.read("INSTALL_V75_PATCHES.ps1"))
        self.assertNotIn('"--repair-joiner-hero-blocks"', dashboard)

    def test_v76_launcher_installs_world_ready_fix_without_proxy_injection(self):
        launcher = self.read("START_V76_WORLD_READY_HERO_STATE_FIX.bat")
        dashboard = self.read("hon_v49_dashboard.py")
        patcher = self.read("PATCH_K2_V76.ps1")
        self.assertIn("INSTALL_V76_PATCHES.ps1", launcher)
        self.assertIn("PATCH_K2_V76.ps1", self.read("INSTALL_V76_PATCHES.ps1"))
        self.assertIn("k2.dll.thorgor_v65_before_v75", patcher)
        self.assertNotIn('"--repair-joiner-hero-blocks"', dashboard)

    def test_v77_launcher_installs_tail_recipient_fix_without_proxy_injection(self):
        launcher = self.read("START_V77_TAIL_RECIPIENT_HERO_FIX.bat")
        dashboard = self.read("hon_v49_dashboard.py")
        patcher = self.read("PATCH_K2_V77.ps1")
        self.assertIn("EnableDelayedExpansion", launcher)
        self.assertIn(
            'if not defined HON_HOME set "HON_HOME=C:\\Program Files (x86)\\Heroes of Newerth"',
            launcher,
        )
        self.assertIn('if not exist "!HON_HOME!\\hon.exe" (', launcher)
        self.assertIn('-HonHome "!HON_HOME!"', launcher)
        self.assertNotIn("if not defined HON_HOME (", launcher)
        self.assertIn("INSTALL_V77_PATCHES.ps1", launcher)
        self.assertIn("PATCH_K2_V77.ps1", self.read("INSTALL_V77_PATCHES.ps1"))
        self.assertIn("PATCH_K2_V65.ps1", patcher)
        self.assertIn("K2 v65 baseline preparation failed", patcher)
        self.assertIn("k2.dll.thorgor_v65_before_v75", patcher)
        self.assertIn("$v76Hash", patcher)
        self.assertNotIn('"--repair-joiner-hero-blocks"', dashboard)

    def test_composable_v77_patch_helpers_return_to_the_parent_installer(self):
        for relative in (
            "FIND_PYTHON.ps1",
            "PATCH_K2_V57.ps1",
            "PATCH_K2_V65.ps1",
            "PATCH_CGAME_V61.ps1",
        ):
            self.assertNotIn("exit 0", self.read(relative), relative)
        self.assertNotIn(
            "K2 v57 baseline installation failed",
            self.read("PATCH_K2_V65.ps1"),
        )


if __name__ == "__main__":
    unittest.main()
