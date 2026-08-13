import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RemoteHostPatcherBundleTests(unittest.TestCase):
    def test_bundle_contains_byte_identical_canonical_patchers(self):
        relative_files = (
            "INSTALL_V61_PATCHES.ps1",
            "PATCH_K2_V57.ps1",
            "PATCH_CGAME_V61.ps1",
            "FIND_PYTHON.ps1",
            "patches/build_k2_v57.py",
            "patches/build_cgame_v61_complete_registry_guard.py",
        )
        for relative in relative_files:
            canonical = (ROOT / relative).read_bytes()
            bundled = (ROOT / "REMOTE HOST" / relative).read_bytes()
            self.assertEqual(canonical, bundled, relative)

    def test_bundle_documents_expected_output_hashes(self):
        readme = (ROOT / "REMOTE HOST" / "README.md").read_text(encoding="utf-8")
        self.assertIn("6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF", readme)
        self.assertIn("88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988", readme)


if __name__ == "__main__":
    unittest.main()
