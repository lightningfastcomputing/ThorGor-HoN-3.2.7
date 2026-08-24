import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = SOURCE_ROOT / "thorgor"


class PortableStackTests(unittest.TestCase):
    def test_package_owns_every_production_entrypoint(self):
        required = (
            "master/server.py",
            "chat/server.py",
            "protocols/game_protocol.py",
            "game_manager/dedicated_slave.py",
            "game_manager/native_match_id.py",
            "game_manager/manager_process.py",
            "tools/dashboard.py",
            "tools/account_manager.py",
            "patches/installer.py",
            "START_STACK.bat",
        )
        for relative in required:
            self.assertTrue((PACKAGE / relative).is_file(), relative)

    def test_copied_package_runs_without_runtime_or_compatibility_layer(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            shutil.copytree(
                PACKAGE,
                parent / "thorgor",
                ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", "runtime", "var", "dashboard_logs"
                ),
            )
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            code = (
                "from pathlib import Path; "
                "from thorgor.paths import ROOT; "
                "assert ROOT == Path.cwd() / 'thorgor' / 'var', ROOT; "
                "from thorgor.master.server import main as master; "
                "from thorgor.chat.server import main as chat; "
                "from thorgor.protocols.game_protocol import main as game; "
                "from thorgor.game_manager.dedicated_slave import main as manager; "
                "from thorgor.tools.dashboard import main as dashboard; "
                "from thorgor.patches.catalog import PatchCatalog; "
                "assert len(PatchCatalog().all()) == 11"
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
