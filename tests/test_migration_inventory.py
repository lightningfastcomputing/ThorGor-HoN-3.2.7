import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "thorgor"


class MigrationInventoryTests(unittest.TestCase):
    def test_compatibility_payload_is_absent(self):
        self.assertFalse((PACKAGE / "compat.py").exists())
        self.assertFalse((PACKAGE / "runtime").exists())

    def test_production_python_has_no_legacy_dynamic_imports(self):
        for path in PACKAGE.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("load_legacy", source, path)
            self.assertNotIn("spec_from_file_location", source, path)
            self.assertNotRegex(source, r"runtime[/\\].*\.py", str(path))

    def test_no_production_python_filename_is_a_historical_revision(self):
        numbered = [
            path.relative_to(PACKAGE).as_posix()
            for path in PACKAGE.rglob("*.py")
            if re.search(r"(?:^|_)v\d+(?:_|\.|$)", path.name, re.IGNORECASE)
        ]
        self.assertEqual(numbered, [])

    def test_dashboard_subprocesses_use_package_modules(self):
        source = (PACKAGE / "tools" / "dashboard.py").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"ROOT\s*/\s*[\"'][^\"']*_v\d+\.py")
        for module in (
            "thorgor.master.server",
            "thorgor.chat.server",
            "thorgor.protocols.game_protocol",
            "thorgor.game_manager.dedicated_slave",
            "thorgor.game_manager.manager_process",
            "thorgor.game_manager.native_match_id",
        ):
            self.assertIn(module, source)


if __name__ == "__main__":
    unittest.main()
