import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_HON_HOME = r"C:\Program Files (x86)\Heroes of Newerth"


class LaunchPathTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_hon_launchers_use_canonical_program_files_home(self):
        launchers = (
            "legacy/1_START_V61_COMPLETE_REGISTRY_GUARD.bat",
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
            "legacy/1_START_V61_COMPLETE_REGISTRY_GUARD.bat",
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
        server = self.read("legacy/1_START_V61_COMPLETE_REGISTRY_GUARD.bat")
        self.assertIn("EnableDelayedExpansion", server)
        self.assertIn('if not exist "!HON_HOME!\\hon.exe" (', server)
        self.assertIn("echo   !HON_HOME!\\hon.exe", server)
        self.assertNotIn("echo   %HON_HOME%\\hon.exe", server)

    def test_runtime_uses_compiled_services_and_host_safe_player_guard(self):
        server = self.read("legacy/1_START_V61_COMPLETE_REGISTRY_GUARD.bat")
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

    def test_refactored_stack_launcher_uses_stable_package_entrypoint(self):
        launcher = self.read("thorgor/START_STACK.bat")
        self.assertIn(r"C:\intelprop\Heroes of Newerth", launcher)
        self.assertIn(r"System32\WindowsPowerShell\v1.0\powershell.exe", launcher)
        self.assertIn(r"PSModulePath=%SystemRoot%\System32\WindowsPowerShell\v1.0\Modules", launcher)
        self.assertIn("INSTALL_V77_PATCHES.ps1", launcher)
        self.assertIn("RESET_V42.ps1", launcher)
        self.assertIn("-m thorgor dashboard", launcher)
        self.assertIn(r"THORGOR_PACKAGE!\runtime", launcher)
        self.assertNotIn(r"set \"THORGOR_ROOT=%~dp0..", launcher)

    def test_staged_dashboard_launches_stable_master_module(self):
        dashboard = self.read("thorgor/runtime/hon_v49_dashboard.py")
        self.assertIn('_module_command("thorgor.master.server")', dashboard)
        self.assertNotIn(
            '_service_command(MASTER_EXE, ROOT / "thorgor_hon_sandboxed_masterserver_v39.py")',
            dashboard,
        )

    def test_staged_dashboard_launches_stable_chat_module(self):
        dashboard = self.read("thorgor/runtime/hon_v49_dashboard.py")
        self.assertIn('_module_command("thorgor.chat.server")', dashboard)
        self.assertNotIn(
            '_service_command(CHAT_EXE, ROOT / "chat-server" / "thorgor_hon_chatserver_v13.py")',
            dashboard,
        )

    def test_staged_dashboard_launches_stable_game_protocol_module(self):
        dashboard = self.read("thorgor/runtime/hon_v49_dashboard.py")
        self.assertIn('_module_command("thorgor.protocols.game_protocol")', dashboard)
        self.assertNotIn(
            '_service_command(UDP_EXE, ROOT / "hon_udp_shim.py")',
            dashboard,
        )

    def test_staged_dashboard_launches_stable_game_manager_modules(self):
        dashboard = self.read("thorgor/runtime/hon_v49_dashboard.py")
        self.assertIn('_module_command("thorgor.game_manager.dedicated_slave")', dashboard)
        self.assertIn('_module_command("thorgor.game_manager.native_match_id")', dashboard)
        self.assertNotIn(
            '_service_command(MANAGER_BRIDGE_EXE, ROOT / "hon_manager_status_bridge_v42.py")',
            dashboard,
        )
        self.assertNotIn(
            '_service_command(NATIVE_BRIDGE_EXE, ROOT / "hon_native_matchid_bridge_v47.py")',
            dashboard,
        )

    def test_v75_launcher_installs_server_side_fix_without_proxy_injection(self):
        launcher = self.read("legacy/START_V75_SERVER_HERO_STATE_FIX.bat")
        dashboard = self.read("hon_v49_dashboard.py")
        self.assertIn("INSTALL_V75_PATCHES.ps1", launcher)
        self.assertIn(
            "PATCH_K2_V75.ps1", self.read("legacy/INSTALL_V75_PATCHES.ps1")
        )
        self.assertNotIn('"--repair-joiner-hero-blocks"', dashboard)

    def test_v76_launcher_installs_world_ready_fix_without_proxy_injection(self):
        launcher = self.read("legacy/START_V76_WORLD_READY_HERO_STATE_FIX.bat")
        dashboard = self.read("hon_v49_dashboard.py")
        patcher = self.read("legacy/PATCH_K2_V76.ps1")
        self.assertIn("INSTALL_V76_PATCHES.ps1", launcher)
        self.assertIn(
            "PATCH_K2_V76.ps1", self.read("legacy/INSTALL_V76_PATCHES.ps1")
        )
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

    def test_retired_root_artifacts_are_archived_under_legacy(self):
        retired = (
            "1_START_V61_COMPLETE_REGISTRY_GUARD.bat",
            "START_V72_DIAGNOSTIC.bat",
            "START_V73_DIAGNOSTIC.bat",
            "START_V74_HERO_LIST_FIX.bat",
            "START_V75_SERVER_HERO_STATE_FIX.bat",
            "START_V76_WORLD_READY_HERO_STATE_FIX.bat",
            "PATCH_K2_V63.ps1",
            "PATCH_K2_V64.ps1",
            "PATCH_K2_V66.ps1",
            "PATCH_K2_V67.ps1",
            "PATCH_K2_V68.ps1",
            "PATCH_K2_V75.ps1",
            "PATCH_K2_V76.ps1",
        )
        for relative in retired:
            self.assertFalse((ROOT / relative).exists(), relative)
            self.assertTrue((ROOT / "legacy" / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
