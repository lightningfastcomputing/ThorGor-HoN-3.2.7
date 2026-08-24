import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ToolsMigrationTests(unittest.TestCase):
    def test_dashboard_has_neutral_product_identity(self):
        source = (ROOT / "thorgor" / "tools" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn('self.title("ThorGor HoN 3.2.7 LAN Sandbox")', source)
        self.assertIn('text="ThorGor HoN 3.2.7 LAN Sandbox"', source)
        self.assertNotIn("Tail-Recipient Hero Fix", source)
        self.assertNotIn("load_legacy", source)

    def test_dashboard_package_entrypoint_smoke(self):
        result = subprocess.run(
            [sys.executable, "-m", "thorgor", "dashboard", "--smoke-test"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_account_manager_is_stable_and_exposed(self):
        source = (ROOT / "thorgor" / "tools" / "account_manager.py").read_text(encoding="utf-8")
        entrypoint = (ROOT / "thorgor" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("from thorgor.master.accounts import AccountStore", source)
        self.assertNotIn("load_legacy", source)
        self.assertIn('args.command == "accounts"', entrypoint)


if __name__ == "__main__":
    unittest.main()
