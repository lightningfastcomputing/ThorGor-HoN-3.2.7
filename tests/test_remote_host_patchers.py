import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RemoteHostPatcherBundleTests(unittest.TestCase):
    def test_bundle_contains_byte_identical_canonical_patchers(self):
        file_pairs = (
            ("INSTALL_V61_PATCHES.ps1", "INSTALL_V61_PATCHES.ps1"),
            ("legacy/INSTALL_V75_PATCHES.ps1", "INSTALL_V75_PATCHES.ps1"),
            ("legacy/INSTALL_V76_PATCHES.ps1", "INSTALL_V76_PATCHES.ps1"),
            ("INSTALL_V77_PATCHES.ps1", "INSTALL_V77_PATCHES.ps1"),
            ("PATCH_K2_V57.ps1", "PATCH_K2_V57.ps1"),
            ("PATCH_K2_V65.ps1", "PATCH_K2_V65.ps1"),
            ("legacy/PATCH_K2_V75.ps1", "PATCH_K2_V75.ps1"),
            ("legacy/PATCH_K2_V76.ps1", "PATCH_K2_V76.ps1"),
            ("PATCH_K2_V77.ps1", "PATCH_K2_V77.ps1"),
            ("PATCH_CGAME_V61.ps1", "PATCH_CGAME_V61.ps1"),
            ("FIND_PYTHON.ps1", "FIND_PYTHON.ps1"),
            ("patches/build_k2_v57.py", "patches/build_k2_v57.py"),
            (
                "patches/build_k2_v65_state_delivery.py",
                "patches/build_k2_v65_state_delivery.py",
            ),
            (
                "patches/build_k2_v75_hero_state_reconciliation.py",
                "patches/build_k2_v75_hero_state_reconciliation.py",
            ),
            (
                "patches/build_k2_v76_world_ready_hero_state_reconciliation.py",
                "patches/build_k2_v76_world_ready_hero_state_reconciliation.py",
            ),
            (
                "patches/build_k2_v77_tail_recipient_hero_fix.py",
                "patches/build_k2_v77_tail_recipient_hero_fix.py",
            ),
            (
                "patches/build_cgame_v61_complete_registry_guard.py",
                "patches/build_cgame_v61_complete_registry_guard.py",
            ),
        )
        for canonical_relative, bundled_relative in file_pairs:
            canonical = (ROOT / canonical_relative).read_bytes()
            bundled = (ROOT / "REMOTE HOST" / bundled_relative).read_bytes()
            self.assertEqual(canonical, bundled, canonical_relative)

    def test_bundle_documents_expected_output_hashes(self):
        readme = (ROOT / "REMOTE HOST" / "README.md").read_text(encoding="utf-8")
        self.assertIn("6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF", readme)
        self.assertIn("82D0363C0BC853ECD60A3AD8A62E01E2BF0897EB1644364FBAC82C7E2B48ECAB", readme)
        self.assertIn("9D731944738C6CA014CB71F25F82DCE8634522247AB935513E2F5A0889C0BFF3", readme)
        self.assertIn("FF25B3EF1D3CCB5F8EE765A036AD6EF6DB984096AAE1E0E97594EDF51A3A3AC0", readme)
        self.assertIn("25B1BB066FE3166BF83A4AA52D6FBB0B9FB972F43161F3D73DFA930090CE7026", readme)
        self.assertIn("88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988", readme)


if __name__ == "__main__":
    unittest.main()
