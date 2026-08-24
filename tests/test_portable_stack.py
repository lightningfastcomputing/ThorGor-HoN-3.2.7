import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = SOURCE_ROOT / "thorgor"
RUNTIME = PACKAGE / "runtime"


class PortableStackTests(unittest.TestCase):
    def test_runtime_payload_matches_verified_source_files(self):
        root_files = (
            "thorgor_hon_sandboxed_masterserver_v39.py",
            "hon_udp_shim.py",
            "hon_manager_status_bridge_v42.py",
            "hon_native_matchid_bridge_v47.py",
            "hon_v49_dashboard.py",
            "manage_accounts_v43.py",
            "INSTALL_V77_PATCHES.ps1",
            "PATCH_K2_V77.ps1",
            "PATCH_K2_V65.ps1",
            "PATCH_K2_V57.ps1",
            "PATCH_CGAME_V61.ps1",
            "FIND_PYTHON.ps1",
            "RESET_V42.ps1",
            "start_manager_v39.ps1",
            "CLEANUP_OLD_TESTS.ps1",
            "2_CHECK_V45.bat",
            "CHECK_RUNTIME.ps1",
        )
        for relative in root_files:
            self.assertEqual(
                (RUNTIME / relative).read_bytes(),
                (SOURCE_ROOT / relative).read_bytes(),
                relative,
            )
        self.assertEqual(
            (RUNTIME / "chat-server" / "thorgor_hon_chatserver_v13.py").read_bytes(),
            (SOURCE_ROOT / "chat-server" / "thorgor_hon_chatserver_v13.py").read_bytes(),
        )
        for source in (SOURCE_ROOT / "patches").glob("build_*.py"):
            self.assertEqual((RUNTIME / "patches" / source.name).read_bytes(), source.read_bytes(), source.name)
        for source in (SOURCE_ROOT / "patches" / "catalog").glob("*.json"):
            self.assertEqual(
                (PACKAGE / "patches" / "catalog_data" / source.name).read_bytes(),
                source.read_bytes(),
                source.name,
            )

    def test_copied_package_loads_legacy_runtime_from_inside_itself(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            shutil.copytree(
                PACKAGE,
                parent / "thorgor",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "work", "dashboard_logs"),
            )
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            code = (
                "from pathlib import Path; "
                "from thorgor.paths import ROOT; "
                "assert ROOT == Path.cwd() / 'thorgor' / 'runtime', ROOT; "
                "from thorgor.compat import load_legacy; "
                "module=load_legacy('portable_udp', 'hon_udp_shim.py'); "
                "assert Path(module.__file__).resolve().parent == ROOT.resolve()"
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=parent,
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
